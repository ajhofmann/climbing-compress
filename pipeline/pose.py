"""Pose detection using MediaPipe Tasks API (PoseLandmarker).

Relies on OpenCV's automatic orientation handling (CAP_PROP_ORIENTATION_AUTO)
so that frames come out in the correct display orientation. No manual rotation.
This ensures pose landmarks are in the same coordinate space as the rendered output.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

from pipeline.smooth import smooth_poses


MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODEL_DIR / "pose_landmarker_heavy.task"

# Landmark indices for climbing (BlazePose 33-point model)
LANDMARKS = {
    "left_wrist": 15,
    "right_wrist": 16,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_hip": 23,
    "right_hip": 24,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_knee": 25,
    "right_knee": 26,
}

# Skeleton connections for drawing
SKELETON_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # arms
    (11, 23), (12, 24), (23, 24),  # torso
    (23, 25), (25, 27), (24, 26), (26, 28),  # legs
]


def _ensure_model() -> str:
    """Download pose landmarker model if not present."""
    if MODEL_PATH.exists():
        return str(MODEL_PATH)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading pose model to {MODEL_PATH}...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Done.")
    return str(MODEL_PATH)


def _resize_for_detection(frame: np.ndarray, max_short_side: int = 640) -> np.ndarray:
    """Resize so the shorter dimension is at most max_short_side."""
    h, w = frame.shape[:2]
    short_side = min(h, w)
    if short_side <= max_short_side:
        return frame
    scale = max_short_side / short_side
    return cv2.resize(frame, (int(w * scale), int(h * scale)))


def extract_poses(
    video_path: str,
    scale: float = 0.5,
    stride: int = 1,
    max_short_side: int = 960,
    progress_cb=None,
) -> tuple:
    """
    Run pose detection on video frames.

    OpenCV handles rotation automatically via ORIENTATION_AUTO.
    No manual rotation is applied, so landmark coordinates are in
    the same space as the display/render output.

    Returns:
        (poses, fps) -- poses has one entry per source frame.
    """
    model_path = _ensure_model()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    vid_options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.3,
        min_tracking_confidence=0.3,
    )

    raw_poses = []

    with vision.PoseLandmarker.create_from_options(vid_options) as landmarker:
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % stride == 0:
                # OpenCV already auto-rotates the frame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_rgb = _resize_for_detection(frame_rgb, max_short_side=max_short_side)

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=frame_rgb,
                )
                timestamp_ms = int(frame_idx * 1000 / fps)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    lm_list = result.pose_landmarks[0]
                    landmarks = {}
                    for name, idx in LANDMARKS.items():
                        lm = lm_list[idx]
                        landmarks[name] = (lm.x, lm.y, lm.visibility)
                    raw_poses.append((frame_idx, landmarks))
                else:
                    raw_poses.append((frame_idx, None))

            frame_idx += 1
            if progress_cb and total_frames > 0:
                progress_cb(frame_idx / total_frames)

    cap.release()

    # Expand to full frame count
    poses = [None] * total_frames
    for fi, pose in raw_poses:
        if fi < total_frames:
            poses[fi] = pose

    if stride > 1:
        poses = interpolate_missing_poses(poses)

    # Temporal smoothing: One Euro Filter kills jitter, stays responsive
    poses = smooth_poses(poses, fps, min_cutoff=1.0, beta=0.5)

    return poses, fps


def interpolate_missing_poses(poses: list) -> list:
    """Fill in missing poses by linear interpolation from neighbors."""
    n = len(poses)
    if n == 0:
        return poses

    first_valid = next((i for i in range(n) if poses[i] is not None), None)
    last_valid = next((i for i in range(n - 1, -1, -1) if poses[i] is not None), None)

    if first_valid is None:
        return poses

    for i in range(first_valid):
        poses[i] = poses[first_valid]
    for i in range(last_valid + 1, n):
        poses[i] = poses[last_valid]

    i = first_valid
    while i < last_valid:
        if poses[i] is None:
            gap_start = i
            while i < last_valid and poses[i] is None:
                i += 1
            gap_end = i
            before = poses[gap_start - 1]
            after = poses[gap_end]
            gap_len = gap_end - gap_start
            for j in range(gap_len):
                t = (j + 1) / (gap_len + 1)
                if isinstance(before, dict):
                    interp = {}
                    for name in before:
                        bx, by, bv = before[name]
                        ax, ay, av = after[name]
                        interp[name] = (bx + t * (ax - bx), by + t * (ay - by), min(bv, av))
                    poses[gap_start + j] = interp
                elif isinstance(before, list):
                    interp = []
                    for k in range(len(before)):
                        bx, by, bv = before[k]
                        ax, ay, av = after[k]
                        interp.append((bx + t * (ax - bx), by + t * (ay - by), min(bv, av)))
                    poses[gap_start + j] = interp
        else:
            i += 1

    return poses
