"""Optical flow with background motion compensation.

Computes dense optical flow (Farneback) and subtracts camera motion
estimated from background pixels outside the climber's bounding box.
This isolates true subject movement from camera shake/panning.

Also provides feature-based camera motion estimation using ORB for
the stabilization pipeline.
"""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
from pipeline.signal import smooth_and_normalize, interpolate_strided
from utils.video_io import iter_video_frames


def compute_flow_scores(
    video_path: str,
    tracks: list[dict | None] | None = None,
    stride: int = 1,
    max_short_side: int = 480,
    smooth_sigma_s: float = 0.3,
    progress_cb: Callable[[float], None] | None = None,
) -> tuple[np.ndarray, float]:
    """Per-frame motion scores using background-compensated optical flow.

    When tracks are provided, subtracts the median background flow
    (camera motion) from the subject region to get true body motion.

    Returns:
        (scores, fps) normalized to [0, 1].
    """
    raw_scores: np.ndarray | None = None
    fps = 0.0
    total_frames = 0
    prev_gray = None

    for frame_idx, gray, meta in iter_video_frames(
        video_path, max_short_side=max_short_side, stride=stride, color="gray",
    ):
        if raw_scores is None:
            fps = meta["fps"]
            total_frames = meta["total_frames"]
            raw_scores = np.zeros(total_frames)

        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2,
                flags=0,
            )

            fh, fw = flow.shape[:2]
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)

            has_track = (
                tracks is not None
                and frame_idx < len(tracks)
                and tracks[frame_idx] is not None
            )

            if has_track:
                bn = tracks[frame_idx].get("bbox_norm")
                if bn:
                    x1, y1, x2, y2 = bn
                    mask_subject = np.zeros((fh, fw), dtype=bool)
                    sx1, sy1 = int(x1 * fw), int(y1 * fh)
                    sx2, sy2 = int(x2 * fw), int(y2 * fh)
                    mask_subject[sy1:sy2, sx1:sx2] = True
                    mask_bg = ~mask_subject

                    # Camera motion = median flow on background
                    if mask_bg.any():
                        bg_fx = float(np.median(flow[mask_bg, 0]))
                        bg_fy = float(np.median(flow[mask_bg, 1]))
                    else:
                        bg_fx, bg_fy = 0.0, 0.0

                    # Subtract camera motion, measure subject residual
                    comp_mag = np.sqrt(
                        (flow[..., 0] - bg_fx) ** 2
                        + (flow[..., 1] - bg_fy) ** 2
                    )

                    if mask_subject.any():
                        raw_scores[frame_idx] = float(
                            np.mean(comp_mag[mask_subject])
                        )
                    else:
                        raw_scores[frame_idx] = float(np.mean(comp_mag))
                else:
                    raw_scores[frame_idx] = float(np.mean(mag))
            else:
                raw_scores[frame_idx] = float(np.mean(mag))

        prev_gray = gray

        if progress_cb and total_frames > 0:
            progress_cb(frame_idx / total_frames)

    if raw_scores is None:
        return np.array([]), 0.0

    if stride > 1:
        raw_scores = interpolate_strided(raw_scores, stride)

    scores = smooth_and_normalize(raw_scores, fps, sigma_s=smooth_sigma_s)
    return scores, fps


def compute_camera_motion(
    video_path: str,
    tracks: list[dict | None] | None = None,
    stride: int = 1,
    max_short_side: int = 480,
    progress_cb: Callable[[float], None] | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Estimate per-frame camera motion using ORB features on background.

    Detects ORB features outside the climber's bounding box, matches
    between consecutive frames, and estimates translation via RANSAC.

    Returns:
        (dx, dy, fps) — per-frame camera translation in normalized [0,1] coords.
        Positive dx = camera moved right, positive dy = camera moved down.
    """
    cam_dx: np.ndarray | None = None
    cam_dy: np.ndarray | None = None
    fps = 0.0
    total_frames = 0

    orb = cv2.ORB_create(nfeatures=500)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    prev_gray = None
    prev_kp = None
    prev_des = None

    for frame_idx, gray, meta in iter_video_frames(
        video_path, max_short_side=max_short_side, stride=stride, color="gray",
    ):
        if cam_dx is None:
            fps = meta["fps"]
            total_frames = meta["total_frames"]
            cam_dx = np.zeros(total_frames)
            cam_dy = np.zeros(total_frames)

        fh, fw = gray.shape[:2]

        # Background mask: exclude the climber bbox (dilated slightly)
        mask = np.ones((fh, fw), dtype=np.uint8) * 255
        if (
            tracks is not None
            and frame_idx < len(tracks)
            and tracks[frame_idx] is not None
        ):
            bn = tracks[frame_idx].get("bbox_norm")
            if bn:
                x1, y1, x2, y2 = bn
                bw_n, bh_n = x2 - x1, y2 - y1
                x1 = max(0, x1 - bw_n * 0.05)
                y1 = max(0, y1 - bh_n * 0.05)
                x2 = min(1, x2 + bw_n * 0.05)
                y2 = min(1, y2 + bh_n * 0.05)
                mask[int(y1 * fh) : int(y2 * fh), int(x1 * fw) : int(x2 * fw)] = 0

        kp, des = orb.detectAndCompute(gray, mask)

        if prev_des is not None and des is not None and len(kp) >= 4:
            matches = bf.match(prev_des, des)

            if len(matches) >= 4:
                src_pts = np.float32([prev_kp[m.queryIdx].pt for m in matches])
                dst_pts = np.float32([kp[m.trainIdx].pt for m in matches])

                _, inlier_mask = cv2.estimateAffinePartial2D(
                    src_pts, dst_pts,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=3.0,
                )

                if inlier_mask is not None:
                    inliers = inlier_mask.flatten().astype(bool)
                    if np.sum(inliers) >= 3:
                        displacements = dst_pts[inliers] - src_pts[inliers]
                        cam_dx[frame_idx] = float(
                            np.median(displacements[:, 0]) / fw
                        )
                        cam_dy[frame_idx] = float(
                            np.median(displacements[:, 1]) / fh
                        )

        prev_gray = gray
        prev_kp = kp
        prev_des = des

        if progress_cb and total_frames > 0 and frame_idx % max(1, total_frames // 50) == 0:
            progress_cb(frame_idx / total_frames)

    if cam_dx is None:
        return np.array([]), np.array([]), 0.0

    if stride > 1:
        cam_dx = interpolate_strided(cam_dx, stride, total_frames=total_frames)
        cam_dy = interpolate_strided(cam_dy, stride, total_frames=total_frames)

    return cam_dx, cam_dy, fps
