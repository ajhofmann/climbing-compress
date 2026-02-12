"""Person detection + tracking for climbing videos.

Uses YOLOv8 (configurable size via YOLO_MODEL constant) for detection
and ByteTrack for multi-frame identity.  Identifies the climber (vs
belayer, spectators) by vertical progress heuristic.

Includes graduated loss-of-track recovery:
  - Three tracking states: LOCKED → SEARCHING → LOST
  - Adaptive max-jump gate that widens as misses accumulate
  - Confidence-gated re-lock for high-confidence detections
  - Rolling quality monitor to detect wrong-person lock-on
  - Fallback re-detection at lower confidence / higher resolution
  - Spatial bias preserved across resets for smarter recovery
  - Configurable via constants in pipeline.constants

Optional dependency — the rest of the pipeline works without it.
"""

from __future__ import annotations

import enum
from collections import deque
from collections.abc import Callable

import numpy as np

from pipeline.constants import (
    BYTETRACK_LOST_TRACK_BUFFER,
    TRACK_EDGE_FILL_MAX_FRAMES,
    TRACK_FALLBACK_CONF,
    TRACK_FALLBACK_RESOLUTION,
    TRACK_LOST_GAP_FRAMES,
    TRACK_MAX_JUMP_NORM,
    TRACK_QUALITY_MIN_CONF,
    TRACK_QUALITY_WINDOW,
    TRACK_RELOCK_CONF,
    TRACK_SEARCH_GAP_FRAMES,
    TRACK_SEARCH_MAX_JUMP_SCALE,
    YOLO_MODEL,
)

try:
    from ultralytics import YOLO
    import supervision as sv
    HAS_TRACKER = True
except ImportError:
    HAS_TRACKER = False


class TrackState(enum.Enum):
    """Graduated tracking states for recovery.

    LOCKED    — confidently tracking the climber, strict spatial gate.
    SEARCHING — lost recently, widened gate + confidence re-lock enabled.
    LOST      — lost for many frames, ByteTrack reset, rely on scoring.
    """
    LOCKED = "locked"
    SEARCHING = "searching"
    LOST = "lost"


_yolo_models: dict[str, "YOLO"] = {}


def _get_yolo(model_name: str = YOLO_MODEL) -> "YOLO":
    """Lazy-load a YOLOv8 model (downloads on first use)."""
    if model_name not in _yolo_models:
        _yolo_models[model_name] = YOLO(model_name)
    return _yolo_models[model_name]


class ClimberTracker:
    """Track persons across frames and identify the climber.

    Uses YOLOv8 for detection and ByteTrack for temporal identity.
    Selects the "climber" track by vertical progress + proximity heuristic.

    Recovery is graduated through three states:

    * **LOCKED** — confidently tracking; strict spatial gate.
    * **SEARCHING** — a few misses; widened gate, confidence re-lock
      enabled, ByteTrack still alive so existing identities persist.
    * **LOST** — many misses; ByteTrack reset, but last known position
      is kept as a soft spatial prior for scoring.

    A rolling quality monitor watches for wrong-person lock-on (low
    confidence, no vertical progress, belayer-like position) and can
    proactively downgrade from LOCKED to SEARCHING.
    """

    def __init__(
        self,
        conf_threshold: float = 0.3,
        frame_rate: int = 30,
        model_name: str | None = None,
    ):
        if not HAS_TRACKER:
            raise ImportError(
                "Install tracking extras: pip install climb-ramp[tracking]"
            )
        # Resolve model file name: accept "yolo11m" or "yolo11m.pt"
        if model_name:
            resolved = model_name if model_name.endswith(".pt") else f"{model_name}.pt"
        else:
            resolved = YOLO_MODEL
        self.model = _get_yolo(resolved)
        self.tracker = sv.ByteTrack(
            track_activation_threshold=conf_threshold,
            lost_track_buffer=BYTETRACK_LOST_TRACK_BUFFER,
            frame_rate=frame_rate,
        )
        self.conf_threshold = conf_threshold
        self.frame_rate = frame_rate
        self.climber_track_id: int | None = None
        self._track_history: dict[int, list[tuple[int, float]]] = {}
        self.last_bbox_norm: tuple[float, float, float, float] | None = None
        self.last_frame_idx: int | None = None
        self.consecutive_misses = 0
        self.state: TrackState = TrackState.LOCKED

        # Rolling quality monitor: recent (confidence, center_y) per detection
        self._quality_window: deque[tuple[float, float]] = deque(
            maxlen=TRACK_QUALITY_WINDOW,
        )

    # -- backward compat property so callers checking .recovery_mode still work --

    @property
    def recovery_mode(self) -> bool:
        """True when tracker is in SEARCHING or LOST state."""
        return self.state in (TrackState.SEARCHING, TrackState.LOST)

    @recovery_mode.setter
    def recovery_mode(self, value: bool) -> None:
        """Allow legacy ``self.recovery_mode = False`` to reset to LOCKED."""
        if not value:
            self.state = TrackState.LOCKED

    def _reset_tracker(self) -> None:
        """Reset ByteTrack and clear per-track identity after a loss.

        Preserves ``last_bbox_norm`` as a soft spatial prior so that
        recovery scoring can still bias toward the last known position.
        """
        self.tracker = sv.ByteTrack(
            track_activation_threshold=self.conf_threshold,
            lost_track_buffer=BYTETRACK_LOST_TRACK_BUFFER,
            frame_rate=self.frame_rate,
        )
        self._track_history = {}
        self.climber_track_id = None
        # NOTE: last_bbox_norm is intentionally kept — it serves as a
        # soft positional prior during LOST-state recovery.

    def _fallback_detect(self, frame_bgr: np.ndarray):
        """Retry detection with lower confidence and higher resolution.

        Called when primary detection misses for 2+ consecutive frames.
        Uses the same model but relaxes the confidence threshold and
        optionally upscales small frames to catch hard-to-detect poses.
        """
        import cv2

        h, w = frame_bgr.shape[:2]
        short_side = min(h, w)

        # Upscale if frame is small relative to the fallback target
        if short_side < TRACK_FALLBACK_RESOLUTION:
            scale = TRACK_FALLBACK_RESOLUTION / short_side
            upscaled = cv2.resize(
                frame_bgr,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            upscaled = frame_bgr

        results = self.model(
            upscaled, classes=[0], conf=TRACK_FALLBACK_CONF, verbose=False
        )[0]
        return sv.Detections.from_ultralytics(results)

    def _register_miss(self) -> None:
        """Track consecutive misses and graduate recovery state."""
        self.consecutive_misses += 1

        if (
            self.state == TrackState.LOCKED
            and self.consecutive_misses >= TRACK_SEARCH_GAP_FRAMES
        ):
            self.state = TrackState.SEARCHING

        if (
            self.state == TrackState.SEARCHING
            and self.consecutive_misses >= TRACK_LOST_GAP_FRAMES
        ):
            self.state = TrackState.LOST
            self._reset_tracker()

    def _check_quality(self, conf: float, center_y: float) -> None:
        """Update rolling quality monitor and downgrade state if needed.

        Watches for wrong-person lock-on by checking recent detection
        confidence.  Low average confidence while LOCKED triggers a
        proactive transition to SEARCHING so the tracker starts looking
        for a better candidate.
        """
        self._quality_window.append((conf, center_y))

        if self.state != TrackState.LOCKED:
            return
        if len(self._quality_window) < TRACK_QUALITY_WINDOW:
            return

        mean_conf = sum(c for c, _ in self._quality_window) / len(self._quality_window)
        mean_y = sum(y for _, y in self._quality_window) / len(self._quality_window)

        # Low confidence streak → probably tracking the wrong person
        # Also flag if tracked person is consistently in the bottom third
        # (likely the belayer standing at the base).
        if mean_conf < TRACK_QUALITY_MIN_CONF or (mean_conf < 0.45 and mean_y > 0.7):
            self.state = TrackState.SEARCHING
            self._quality_window.clear()

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        frame_idx: int,
    ) -> dict | None:
        """Detect and track persons in a single frame.

        Returns dict with:
            bbox: (x1, y1, x2, y2) pixel coords
            bbox_norm: (x1, y1, x2, y2) in [0,1]
            track_id: int
            confidence: float
            n_persons: total persons detected
        Or None if no person detected.
        """
        h, w = frame_bgr.shape[:2]

        results = self.model(
            frame_bgr, classes=[0], conf=self.conf_threshold, verbose=False
        )[0]
        detections = sv.Detections.from_ultralytics(results)

        # Fallback: if primary detection missed entirely, retry with
        # lower confidence and optionally higher resolution.
        if len(detections) == 0 and self.consecutive_misses >= 2:
            detections = self._fallback_detect(frame_bgr)

        if len(detections) == 0:
            self._register_miss()
            return None

        tracked = self.tracker.update_with_detections(detections)

        if len(tracked) == 0:
            self._register_miss()
            return None

        # Update vertical position history per track
        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i]
            center_y = (bbox[1] + bbox[3]) / 2 / h
            if tid not in self._track_history:
                self._track_history[tid] = []
            self._track_history[tid].append((frame_idx, center_y))

        climber_idx = self._select_climber(tracked, h, w, frame_idx)
        if climber_idx is None:
            self._register_miss()
            return None

        bbox = tracked.xyxy[climber_idx]
        track_id = int(tracked.tracker_id[climber_idx])
        conf = float(tracked.confidence[climber_idx])
        bbox_norm = (
            float(bbox[0] / w),
            float(bbox[1] / h),
            float(bbox[2] / w),
            float(bbox[3] / h),
        )
        recovered = self.state in (TrackState.SEARCHING, TrackState.LOST)

        # Quality monitor: feed the detection before resetting state
        center_y_norm = (bbox_norm[1] + bbox_norm[3]) / 2
        self._check_quality(conf, center_y_norm)

        self.consecutive_misses = 0
        # Only go back to LOCKED if we were SEARCHING/LOST
        if self.state in (TrackState.SEARCHING, TrackState.LOST):
            self.state = TrackState.LOCKED
            self._quality_window.clear()
        self.last_bbox_norm = bbox_norm
        self.last_frame_idx = frame_idx
        self.climber_track_id = track_id

        return {
            "bbox": (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
            "bbox_norm": bbox_norm,
            "track_id": track_id,
            "confidence": conf,
            "n_persons": len(tracked),
            "recovered": recovered,
        }

    def _select_climber(self, tracked, h: int, w: int, frame_idx: int) -> int | None:
        """Pick the climber from tracked persons.

        Heuristics in priority order:
        1. Continuity — keep the previously identified climber track
        2. Confidence re-lock — in SEARCHING/LOST, accept a high-conf
           detection regardless of distance (handles camera cuts/pans)
        3. Scored selection — vertical progress, height, size, proximity
        """
        if len(tracked) == 0:
            return None

        last_bbox = self.last_bbox_norm
        frame_gap = 1
        if self.last_frame_idx is not None and frame_idx > self.last_frame_idx:
            frame_gap = max(1, frame_idx - self.last_frame_idx)

        # Adaptive max_jump: widens as misses accumulate
        miss_scale = 1.0 + self.consecutive_misses * 0.3
        if self.state == TrackState.SEARCHING:
            miss_scale = max(miss_scale, TRACK_SEARCH_MAX_JUMP_SCALE)
        base_jump = TRACK_MAX_JUMP_NORM * frame_gap * miss_scale
        max_jump = min(base_jump, 0.9)

        is_recovering = self.state in (TrackState.SEARCHING, TrackState.LOST)

        def _center_dist(bbox: np.ndarray) -> float:
            if last_bbox is None:
                return 0.0
            cx = (bbox[0] + bbox[2]) / 2 / w
            cy = (bbox[1] + bbox[3]) / 2 / h
            last_cx = (last_bbox[0] + last_bbox[2]) / 2
            last_cy = (last_bbox[1] + last_bbox[3]) / 2
            return float(np.hypot(cx - last_cx, cy - last_cy))

        # Continuity: keep the same track if still visible and plausible
        if self.climber_track_id is not None:
            for i, tid in enumerate(tracked.tracker_id):
                if int(tid) == self.climber_track_id:
                    dist = _center_dist(tracked.xyxy[i])
                    if is_recovering or last_bbox is None or dist <= max_jump:
                        return i
                    break

        # Confidence-gated re-lock: in SEARCHING/LOST state, accept a
        # high-confidence, large, upper-frame detection without distance
        # constraint.  Handles camera cuts and pans.
        if is_recovering and len(tracked) > 0:
            best_relock_idx: int | None = None
            best_relock_score = -float("inf")

            for i in range(len(tracked.tracker_id)):
                conf = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
                if conf < TRACK_RELOCK_CONF:
                    continue
                bbox = tracked.xyxy[i]
                center_y = (bbox[1] + bbox[3]) / 2 / h
                area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / (w * h)
                # Prefer higher (lower y), larger, more confident
                relock_score = conf * 2.0 + (1.0 - center_y) * 1.5 + area * 1.0
                if relock_score > best_relock_score:
                    best_relock_score = relock_score
                    best_relock_idx = i

            if best_relock_idx is not None:
                self.climber_track_id = int(tracked.tracker_id[best_relock_idx])
                return best_relock_idx

        # Score each track
        best_idx: int | None = None
        best_score = -float("inf")

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i]

            dist = _center_dist(bbox)
            if last_bbox is not None and dist > max_jump and not is_recovering:
                continue

            # Vertical progress: how much has center_y decreased (moved up)?
            progress = 0.0
            history = self._track_history.get(tid, [])
            if len(history) >= 2:
                progress = history[0][1] - history[-1][1]  # positive = up

            # Position: higher on wall = lower y = better
            center_y = (bbox[1] + bbox[3]) / 2 / h
            height_score = 1.0 - center_y

            # Size: larger = more prominent
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / (w * h)

            # Proximity: prefer candidates near the last bbox (soft bias
            # even after reset, since last_bbox_norm is preserved)
            proximity = 0.0
            if last_bbox is not None and max_jump > 0:
                proximity = max(0.0, 1.0 - min(dist / max_jump, 1.0))

            conf = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0

            score = (
                progress * 3.0
                + height_score * 1.0
                + area * 0.5
                + proximity * 1.5
                + conf * 0.5
            )

            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is None:
            return None

        self.climber_track_id = int(tracked.tracker_id[best_idx])
        return best_idx


def track_video(
    video_path: str,
    stride: int = 1,
    max_short_side: int = 640,
    progress_cb: Callable[[float], None] | None = None,
    model_name: str | None = None,
) -> tuple[list[dict | None], float]:
    """Run person tracking on entire video.

    Args:
        model_name: YOLO model to use (e.g. "yolo11m").  Appends ".pt"
            automatically.  Falls back to YOLO_MODEL constant if None.

    Returns:
        (tracks, fps) where tracks[i] is the tracking result for frame i,
        or None if no person was detected in that frame.
    """
    if not HAS_TRACKER:
        return [], 0.0

    from utils.video_io import iter_video_frames

    fps = 0.0
    total_frames = 0
    max_frame_idx = -1
    tracker: ClimberTracker | None = None
    results: list[dict | None] | None = None

    for frame_idx, frame, meta in iter_video_frames(
        video_path, max_short_side=max_short_side, stride=stride, color="bgr",
    ):
        if results is None:
            fps = meta["fps"]
            total_frames = meta["total_frames"]
            tracker = ClimberTracker(
                frame_rate=int(fps) or 30,
                model_name=model_name,
            )
            results = [None] * total_frames

        max_frame_idx = max(max_frame_idx, frame_idx)

        # Extend results if actual frames exceed metadata count
        if frame_idx >= len(results):
            results.extend([None] * (frame_idx - len(results) + 1))

        result = tracker.process_frame(frame, frame_idx)
        results[frame_idx] = result

        if progress_cb and total_frames > 0:
            progress_cb(frame_idx / total_frames)

    if results is None:
        return [], 0.0

    if stride > 1:
        results = _interpolate_tracks(results)

    return results, fps


def _interpolate_tracks(tracks: list[dict | None]) -> list[dict | None]:
    """Fill gaps from stride by linearly interpolating bounding boxes."""
    n = len(tracks)
    if n == 0:
        return tracks

    valid = [(i, t) for i, t in enumerate(tracks) if t is not None]
    if len(valid) < 2:
        return tracks

    def _mark_interpolated(track: dict) -> dict:
        return {**track, "interpolated": True}

    # Interpolate between consecutive valid frames
    for vi in range(len(valid) - 1):
        i1, t1 = valid[vi]
        i2, t2 = valid[vi + 1]

        if i2 - i1 <= 1:
            continue
        if i2 - i1 - 1 > TRACK_EDGE_FILL_MAX_FRAMES:
            continue
        if t1.get("bbox_norm") is None or t2.get("bbox_norm") is None:
            continue

        b1 = np.array(t1["bbox_norm"])
        b2 = np.array(t2["bbox_norm"])

        for j in range(i1 + 1, i2):
            alpha = (j - i1) / (i2 - i1)
            bbox_interp = tuple((b1 * (1 - alpha) + b2 * alpha).tolist())
            tracks[j] = {
                "bbox_norm": bbox_interp,
                "track_id": t1["track_id"],
                "confidence": min(t1["confidence"], t2["confidence"]),
                "n_persons": t1.get("n_persons", 1),
                "interpolated": True,
            }

    # Forward/backward fill edges
    first_idx = valid[0][0]
    if first_idx > 0:
        edge = min(first_idx, TRACK_EDGE_FILL_MAX_FRAMES)
        for i in range(first_idx - edge, first_idx):
            tracks[i] = _mark_interpolated(valid[0][1])
    last_idx = valid[-1][0]
    if last_idx < n - 1:
        edge = min(n - 1 - last_idx, TRACK_EDGE_FILL_MAX_FRAMES)
        for i in range(last_idx + 1, last_idx + 1 + edge):
            tracks[i] = _mark_interpolated(valid[-1][1])

    return tracks


def crop_frame_to_track(
    frame: np.ndarray,
    track: dict,
    margin: float = 0.15,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Crop a frame to the tracked person's bounding box with margin.

    Returns:
        (cropped_frame, (x1, y1, x2, y2)) in pixel coords of the crop.
    """
    from utils.bbox import crop_to_bbox

    h, w = frame.shape[:2]
    crop, (x_off, y_off, cw, ch) = crop_to_bbox(
        frame, track["bbox_norm"], margin=margin,
    )
    # Convert normalised origin to pixel coords for backward compat
    x1 = int(x_off * w)
    y1 = int(y_off * h)
    x2 = x1 + crop.shape[1]
    y2 = y1 + crop.shape[0]
    return crop, (x1, y1, x2, y2)
