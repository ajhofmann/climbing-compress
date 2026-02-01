"""Overlays for rendered video — speed badge (always-on) and full debug."""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.pose import SKELETON_CONNECTIONS


def make_speed_badge_fn(speed_curve: np.ndarray):
    """
    Create a lightweight speed-indicator overlay (always-on).

    Shows a small rounded badge in the top-right with the current
    speed multiplier, color-coded green/yellow/red.

    Returns: fn(frame_rgb, src_frame_idx, speed) -> frame_rgb
    """

    def badge(frame: np.ndarray, src_idx: int, speed: float) -> np.ndarray:
        h, w = frame.shape[:2]

        speed_text = f"{speed:.1f}x"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.55, h / 900)
        thickness = max(1, int(h / 500))

        text_size = cv2.getTextSize(speed_text, font, font_scale, thickness)[0]
        tw, th = text_size

        # Position: top-right with padding
        pad = 8
        margin = 10
        bx1 = w - tw - pad * 2 - margin
        by1 = margin
        bx2 = w - margin
        by2 = margin + th + pad * 2

        # Semi-transparent rounded background
        overlay = frame.copy()
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        # Color: green < 1.5x, yellow 1.5-4x, warm red > 4x
        if speed <= 1.5:
            color = (110, 220, 140)   # sage green
        elif speed <= 4.0:
            color = (220, 200, 110)   # warm amber
        else:
            color = (210, 130, 100)   # muted terracotta

        tx = bx1 + pad
        ty = by2 - pad

        cv2.putText(frame, speed_text, (tx, ty), font, font_scale,
                    color, thickness, cv2.LINE_AA)

        return frame

    return badge


def make_debug_overlay_fn(
    poses: list,
    scores: np.ndarray,
    speed_curve: np.ndarray,
    fps: float,
):
    """
    Full debug overlay: skeleton + speed badge + frame counter + score bar.

    Returns: fn(frame_rgb, src_frame_idx, speed) -> frame_rgb
    """

    badge_fn = make_speed_badge_fn(speed_curve)

    def overlay(frame: np.ndarray, src_idx: int, speed: float) -> np.ndarray:
        h, w = frame.shape[:2]

        # 1. Skeleton
        if src_idx < len(poses) and poses[src_idx] is not None:
            pose = poses[src_idx]

            if isinstance(pose, dict):
                from pipeline.pose import LANDMARKS
                idx_to_pt = {}
                for name, lm_idx in LANDMARKS.items():
                    if name in pose:
                        x, y, vis = pose[name]
                        if vis > 0.3:
                            idx_to_pt[lm_idx] = (int(x * w), int(y * h))

                for i1, i2 in SKELETON_CONNECTIONS:
                    if i1 in idx_to_pt and i2 in idx_to_pt:
                        cv2.line(frame, idx_to_pt[i1], idx_to_pt[i2],
                                 (0, 255, 200), 2, cv2.LINE_AA)
                for pt in idx_to_pt.values():
                    cv2.circle(frame, pt, 4, (255, 100, 100), -1, cv2.LINE_AA)

            elif isinstance(pose, list) and len(pose) == 33:
                pts = {}
                for i, (x, y, vis) in enumerate(pose):
                    if vis > 0.3:
                        pts[i] = (int(x * w), int(y * h))
                for i1, i2 in SKELETON_CONNECTIONS:
                    if i1 in pts and i2 in pts:
                        cv2.line(frame, pts[i1], pts[i2],
                                 (0, 255, 200), 2, cv2.LINE_AA)
                for pt in pts.values():
                    cv2.circle(frame, pt, 4, (255, 100, 100), -1, cv2.LINE_AA)

        # 2. Speed badge
        frame = badge_fn(frame, src_idx, speed)

        # 3. Frame counter (top-left)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.5, h / 900)
        src_time = src_idx / fps if fps > 0 else 0
        frame_text = f"f{src_idx} | {src_time:.1f}s"
        tw = int(len(frame_text) * 10 * font_scale)
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (tw + 15, 35), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
        cv2.putText(frame, frame_text, (10, 28), font, font_scale * 0.65,
                    (200, 200, 200), 1, cv2.LINE_AA)

        # 4. Movement score bar (bottom)
        if src_idx < len(scores):
            score = float(scores[src_idx])
            bar_h = max(4, int(h * 0.012))
            bar_y = h - bar_h
            frame[bar_y:h, :] = (30, 30, 30)
            bar_w = int(w * score)
            r = int(200 * (1 - score) + 50)
            g = int(200 * score + 50)
            if bar_w > 0:
                frame[bar_y:h, :bar_w] = (r, g, 80)

        return frame

    return overlay


# Backward compat alias
make_overlay_fn = make_debug_overlay_fn
