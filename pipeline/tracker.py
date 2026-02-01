"""Person detection + tracking for climbing videos.

Uses YOLOv8 for detection and ByteTrack for multi-frame identity.
Identifies the climber (vs belayer, spectators) by vertical progress
heuristic: the person moving highest on the wall over time.

Optional dependency — the rest of the pipeline works without it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

try:
    from ultralytics import YOLO
    import supervision as sv
    HAS_TRACKER = True
except ImportError:
    HAS_TRACKER = False


_yolo_model = None


def _get_yolo():
    """Lazy-load YOLOv8 nano model (downloads on first use)."""
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO("yolov8n.pt")
    return _yolo_model


class ClimberTracker:
    """Track persons across frames and identify the climber.

    Uses YOLOv8 for detection and ByteTrack for temporal identity.
    Selects the "climber" track by vertical progress heuristic.
    """

    def __init__(self, conf_threshold: float = 0.3, frame_rate: int = 30):
        if not HAS_TRACKER:
            raise ImportError(
                "Install tracking extras: pip install climb-ramp[tracking]"
            )
        self.model = _get_yolo()
        self.tracker = sv.ByteTrack(
            track_activation_threshold=conf_threshold,
            frame_rate=frame_rate,
        )
        self.conf_threshold = conf_threshold
        self.climber_track_id: int | None = None
        self._track_history: dict[int, list[tuple[int, float]]] = {}

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

        if len(detections) == 0:
            return None

        tracked = self.tracker.update_with_detections(detections)

        if len(tracked) == 0:
            return None

        # Update vertical position history per track
        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i]
            center_y = (bbox[1] + bbox[3]) / 2 / h
            if tid not in self._track_history:
                self._track_history[tid] = []
            self._track_history[tid].append((frame_idx, center_y))

        climber_idx = self._select_climber(tracked, h, w)

        bbox = tracked.xyxy[climber_idx]
        track_id = int(tracked.tracker_id[climber_idx])
        conf = float(tracked.confidence[climber_idx])

        return {
            "bbox": (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
            "bbox_norm": (
                float(bbox[0] / w),
                float(bbox[1] / h),
                float(bbox[2] / w),
                float(bbox[3] / h),
            ),
            "track_id": track_id,
            "confidence": conf,
            "n_persons": len(tracked),
        }

    def _select_climber(self, tracked, h: int, w: int) -> int:
        """Pick the climber from tracked persons.

        Heuristics in priority order:
        1. Continuity — keep the previously identified climber track
        2. Vertical progress — most upward motion over time
        3. Height — highest position in frame (lowest y)
        4. Size — largest bounding box (closest to camera, on wall)
        """
        if len(tracked) == 1:
            self.climber_track_id = int(tracked.tracker_id[0])
            return 0

        # Continuity: keep the same track if still visible
        if self.climber_track_id is not None:
            for i, tid in enumerate(tracked.tracker_id):
                if int(tid) == self.climber_track_id:
                    return i

        # Score each track
        best_idx = 0
        best_score = -float("inf")

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i]

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

            score = progress * 3.0 + height_score * 1.0 + area * 0.5

            if score > best_score:
                best_score = score
                best_idx = i

        self.climber_track_id = int(tracked.tracker_id[best_idx])
        return best_idx


def track_video(
    video_path: str,
    stride: int = 1,
    max_short_side: int = 640,
    progress_cb: Callable[[float], None] | None = None,
) -> tuple[list[dict | None], float]:
    """Run person tracking on entire video.

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
            tracker = ClimberTracker(frame_rate=int(fps) or 30)
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

    # Interpolate between consecutive valid frames
    for vi in range(len(valid) - 1):
        i1, t1 = valid[vi]
        i2, t2 = valid[vi + 1]

        if i2 - i1 <= 1:
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
    if valid[0][0] > 0:
        for i in range(valid[0][0]):
            tracks[i] = valid[0][1]
    if valid[-1][0] < n - 1:
        for i in range(valid[-1][0] + 1, n):
            tracks[i] = valid[-1][1]

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
