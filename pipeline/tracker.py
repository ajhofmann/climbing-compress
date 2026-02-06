"""Person detection + tracking for climbing videos.

Uses YOLOv8 (configurable size via YOLO_MODEL constant) for detection
and ByteTrack for multi-frame identity.  Identifies the climber (vs
belayer, spectators) by vertical progress heuristic.

Includes loss-of-track recovery:
  - Consecutive miss counter with automatic ByteTrack reinit
  - Max-jump gate to reject identity switches
  - Fallback re-detection at lower confidence / higher resolution
  - Configurable via constants in pipeline.constants

Optional dependency — the rest of the pipeline works without it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from pipeline.constants import (
    BYTETRACK_LOST_TRACK_BUFFER,
    TRACK_EDGE_FILL_MAX_FRAMES,
    TRACK_FALLBACK_CONF,
    TRACK_FALLBACK_RESOLUTION,
    TRACK_LOST_GAP_FRAMES,
    TRACK_MAX_JUMP_NORM,
    YOLO_MODEL,
)

try:
    from ultralytics import YOLO
    import supervision as sv
    HAS_TRACKER = True
except ImportError:
    HAS_TRACKER = False


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
    Includes fallback re-detection and automatic recovery on loss.
    """

    def __init__(
        self,
        conf_threshold: float = 0.3,
        frame_rate: int = 30,
        model_name: str | None = None,
        strategy: str = "auto",
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
        self.strategy = strategy
        self.climber_track_id: int | None = None
        self._track_history: dict[int, list[tuple[int, float]]] = {}
        self.last_bbox_norm: tuple[float, float, float, float] | None = None
        self.last_frame_idx: int | None = None
        self.consecutive_misses = 0
        self.recovery_mode = False

    def _reset_tracker(self) -> None:
        """Reset ByteTrack and clear per-track history after a loss."""
        self.tracker = sv.ByteTrack(
            track_activation_threshold=self.conf_threshold,
            lost_track_buffer=BYTETRACK_LOST_TRACK_BUFFER,
            frame_rate=self.frame_rate,
        )
        self._track_history = {}
        self.climber_track_id = None
        self.last_bbox_norm = None
        self.last_frame_idx = None

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
        """Track consecutive misses and enter recovery when threshold hit."""
        self.consecutive_misses += 1
        if self.consecutive_misses >= TRACK_LOST_GAP_FRAMES and not self.recovery_mode:
            self.recovery_mode = True
            self._reset_tracker()

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
        recovered = self.recovery_mode

        self.consecutive_misses = 0
        self.recovery_mode = False
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
        2. Vertical progress — most upward motion over time
        3. Height — highest position in frame (lowest y)
        4. Size — largest bounding box (closest to camera, on wall)
        """
        if len(tracked) == 0:
            return None

        if self.strategy != "auto":
            return self._select_by_strategy(tracked, h, w)

        last_bbox = self.last_bbox_norm
        frame_gap = 1
        if self.last_frame_idx is not None and frame_idx > self.last_frame_idx:
            frame_gap = max(1, frame_idx - self.last_frame_idx)
        max_jump = min(TRACK_MAX_JUMP_NORM * frame_gap, 0.9)

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
                    if self.recovery_mode or last_bbox is None or dist <= max_jump:
                        return i
                    break

        # Score each track
        best_idx: int | None = None
        best_score = -float("inf")

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i]

            dist = _center_dist(bbox)
            if last_bbox is not None and dist > max_jump and not self.recovery_mode:
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

            # Proximity: prefer candidates near the last bbox
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

    def _select_by_strategy(self, tracked, h: int, w: int) -> int | None:
        """Select subject based on a fixed strategy (highest/leftmost/etc)."""
        best_idx: int | None = None
        best_score: float | None = None

        for i, _track_id in enumerate(tracked.tracker_id):
            bbox = tracked.xyxy[i]
            center_x = (bbox[0] + bbox[2]) / 2 / w
            center_y = (bbox[1] + bbox[3]) / 2 / h
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / (w * h)

            if self.strategy == "highest":
                score = -center_y
            elif self.strategy == "largest":
                score = area
            elif self.strategy == "leftmost":
                score = -center_x
            elif self.strategy == "rightmost":
                score = center_x
            else:
                score = area

            if best_score is None or score > best_score:
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
    strategy: str = "auto",
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
                strategy=strategy,
            )
            results = [None] * total_frames

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
