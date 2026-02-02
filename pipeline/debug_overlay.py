"""Overlays for rendered video — speed badge (always-on) and full debug.

Debug layers:
  1. Skeleton — pose landmarks + connections, color-coded by visibility
  2. Tracking bbox — dashed bounding box from person tracker
  3. COM trail — center-of-mass path trailing behind the climber
  4. Speed badge — top-right speed multiplier (always-on)
  5. Frame counter — top-left frame number, time, and mode
  6. Rest badge — center-top indicator when in a rest section
  7. Score bars — thin horizontal meters for pose + flow scores
  8. Timeline strip — full-video overview of speed, scores, rest, pins
  9. Stabilization inset — mini offset magnitude plot
"""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np

from pipeline.constants import MIN_VISIBILITY
from pipeline.pose import SKELETON_CONNECTIONS, LANDMARKS
from pipeline.speed_curve import get_time_mapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _speed_color(speed: float) -> tuple[int, int, int]:
    """Speed -> RGB.  Slow = sage green, mid = amber, fast = terracotta."""
    if speed <= 1.5:
        return (110, 220, 140)
    elif speed <= 4.0:
        return (220, 200, 110)
    else:
        return (210, 130, 100)


def _semi_rect(frame: np.ndarray, pt1: tuple, pt2: tuple,
               color: tuple, alpha: float = 0.65) -> None:
    """Draw a semi-transparent filled rectangle."""
    ov = frame.copy()
    cv2.rectangle(ov, pt1, pt2, color, -1)
    cv2.addWeighted(ov, alpha, frame, 1.0 - alpha, 0, frame)


def _stab_coord_adjuster(
    stab_offsets: tuple[np.ndarray, np.ndarray],
    stabilize_crop: float,
) -> Callable[[float, float, int, int, int], tuple[float, float]]:
    """Return a function that remaps normalized [0,1] coords to the cropped frame.

    After stabilization, the rendered frame is a crop of a padded decode.
    Pose landmarks are in [0,1] of the original frame; this adjusts them
    so ``(adj_x * w, adj_y * h)`` lands at the correct pixel in the crop.
    """
    stab_dx, stab_dy = stab_offsets
    pad_ratio = 1.0 / (1.0 - stabilize_crop)

    def adjust(norm_x: float, norm_y: float,
               src_idx: int, h: int, w: int) -> tuple[float, float]:
        pad_w = w * pad_ratio
        pad_h = h * pad_ratio
        margin_w = (pad_w - w) / 2
        margin_h = (pad_h - h) / 2
        dx = float(stab_dx[src_idx]) if src_idx < len(stab_dx) else 0.0
        dy = float(stab_dy[src_idx]) if src_idx < len(stab_dy) else 0.0
        crop_x = margin_w + dx * pad_w
        crop_y = margin_h + dy * pad_h
        # Clamp to match render.py
        crop_x = max(0, min(crop_x, pad_w - w))
        crop_y = max(0, min(crop_y, pad_h - h))
        adj_x = (norm_x * pad_w - crop_x) / w
        adj_y = (norm_y * pad_h - crop_y) / h
        return adj_x, adj_y

    return adjust


# ---------------------------------------------------------------------------
# Layer 1: Skeleton with visibility quality
# ---------------------------------------------------------------------------

def _draw_skeleton(frame: np.ndarray, pose, h: int, w: int) -> None:
    if pose is None:
        return

    if isinstance(pose, dict):
        idx_to_pt: dict[int, tuple[int, int]] = {}
        idx_to_vis: dict[int, float] = {}
        for name, lm_idx in LANDMARKS.items():
            if name in pose:
                x, y, vis = pose[name]
                if vis > MIN_VISIBILITY:
                    idx_to_pt[lm_idx] = (int(x * w), int(y * h))
                    idx_to_vis[lm_idx] = vis

        # Bones — brighter when both endpoints are confident
        for i1, i2 in SKELETON_CONNECTIONS:
            if i1 in idx_to_pt and i2 in idx_to_pt:
                v = min(idx_to_vis.get(i1, 0), idx_to_vis.get(i2, 0))
                if v > 0.7:
                    color = (0, 255, 200)    # confident: cyan-green
                elif v > 0.5:
                    color = (0, 210, 190)    # moderate: teal
                else:
                    color = (0, 160, 160)    # low: dim teal
                cv2.line(frame, idx_to_pt[i1], idx_to_pt[i2],
                         color, 2, cv2.LINE_AA)

        # Joints — orange tint when low-visibility
        for idx, pt in idx_to_pt.items():
            vis = idx_to_vis.get(idx, 0.5)
            if vis > 0.7:
                cv2.circle(frame, pt, 4, (255, 100, 100), -1, cv2.LINE_AA)
            else:
                cv2.circle(frame, pt, 3, (220, 150, 60), -1, cv2.LINE_AA)

    elif isinstance(pose, list) and len(pose) == 33:
        pts: dict[int, tuple[int, int]] = {}
        for i, (x, y, vis) in enumerate(pose):
            if vis > MIN_VISIBILITY:
                pts[i] = (int(x * w), int(y * h))
        for i1, i2 in SKELETON_CONNECTIONS:
            if i1 in pts and i2 in pts:
                cv2.line(frame, pts[i1], pts[i2],
                         (0, 255, 200), 2, cv2.LINE_AA)
        for pt in pts.values():
            cv2.circle(frame, pt, 4, (255, 100, 100), -1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Layer 2: Tracking bounding box
# ---------------------------------------------------------------------------

def _draw_tracking_bbox(frame: np.ndarray, track: dict | None,
                        h: int, w: int) -> None:
    if track is None:
        return
    bn = track.get("bbox_norm")
    if bn is None:
        return

    x1, y1, x2, y2 = bn
    px1, py1 = int(x1 * w), int(y1 * h)
    px2, py2 = int(x2 * w), int(y2 * h)
    color = (180, 170, 70)      # muted gold
    thick = max(1, int(h / 600))

    # Dashed rectangle
    dash = max(6, int(h * 0.012))
    for a, b in [
        ((px1, py1), (px2, py1)),   # top
        ((px2, py1), (px2, py2)),   # right
        ((px1, py2), (px2, py2)),   # bottom
        ((px1, py1), (px1, py2)),   # left
    ]:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = max(1, int(np.hypot(dx, dy)))
        n_seg = max(1, length // (dash * 2))
        for k in range(n_seg):
            t0 = k / n_seg
            t1 = min((k + 0.5) / n_seg, 1.0)
            s = (int(a[0] + dx * t0), int(a[1] + dy * t0))
            e = (int(a[0] + dx * t1), int(a[1] + dy * t1))
            cv2.line(frame, s, e, color, thick, cv2.LINE_AA)

    # Tiny label
    n_persons = track.get("n_persons", 1)
    label = f"T{track.get('track_id', '?')}"
    if n_persons > 1:
        label += f"  {n_persons}p"
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = max(0.32, h / 1600)
    tw_t, th_t = cv2.getTextSize(label, font, fs, 1)[0]
    lx = px1
    ly = py1 - th_t - 6
    if ly < 0:
        ly = py2 + 2
    _semi_rect(frame, (lx, ly), (lx + tw_t + 6, ly + th_t + 4),
               (20, 20, 20), 0.6)
    cv2.putText(frame, label, (lx + 3, ly + th_t + 1),
                font, fs, color, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Layer 3: Center-of-mass trail
# ---------------------------------------------------------------------------

def _compute_com(poses: list) -> tuple[np.ndarray, np.ndarray]:
    """Center-of-mass x, y arrays (normalized). NaN-gaps interpolated."""
    n = len(poses)
    cx = np.full(n, np.nan)
    cy = np.full(n, np.nan)
    parts = ("left_hip", "right_hip", "left_shoulder", "right_shoulder")

    for i, p in enumerate(poses):
        if p is None or not isinstance(p, dict):
            continue
        xs, ys = [], []
        for name in parts:
            if name in p:
                x, y, v = p[name]
                if v > MIN_VISIBILITY:
                    xs.append(x)
                    ys.append(y)
        if len(xs) >= 2:
            cx[i] = np.mean(xs)
            cy[i] = np.mean(ys)

    valid = ~np.isnan(cx)
    if np.sum(valid) < 2:
        return cx, cy
    idx = np.arange(n)
    cx = np.interp(idx, idx[valid], cx[valid])
    cy = np.interp(idx, idx[valid], cy[valid])
    return cx, cy


def _draw_com_trail(frame: np.ndarray, cx: np.ndarray, cy: np.ndarray,
                    src_idx: int, h: int, w: int,
                    speed_curve: np.ndarray, trail: int = 40) -> None:
    lo = max(0, src_idx - trail)
    hi = min(src_idx + 1, len(cx))
    if hi <= lo:
        return

    pts: list[tuple[int, int, int]] = []
    for i in range(lo, hi):
        if i >= len(cx) or np.isnan(cx[i]):
            continue
        pts.append((int(cx[i] * w), int(cy[i] * h), i))
    if len(pts) < 2:
        return

    for j in range(1, len(pts)):
        x0, y0, _ = pts[j - 1]
        x1, y1, fi = pts[j]
        alpha = j / len(pts)
        spd = float(speed_curve[fi]) if fi < len(speed_curve) else 1.0
        base = _speed_color(spd)
        col = tuple(int(c * (0.25 + 0.75 * alpha)) for c in base)
        thick = max(1, int(1 + alpha * 1.5))
        cv2.line(frame, (x0, y0), (x1, y1), col, thick, cv2.LINE_AA)

    # Current position dot
    x, y, _ = pts[-1]
    cv2.circle(frame, (x, y), 5, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 5, (60, 60, 60), 1, cv2.LINE_AA)


def _draw_com_trail_adjusted(
    frame: np.ndarray, cx: np.ndarray, cy: np.ndarray,
    src_idx: int, h: int, w: int,
    speed_curve: np.ndarray,
    adjust: Callable,
    trail: int = 40,
) -> None:
    """COM trail with per-point stabilization coordinate adjustment."""
    lo = max(0, src_idx - trail)
    hi = min(src_idx + 1, len(cx))
    if hi <= lo:
        return

    pts: list[tuple[int, int, int]] = []
    for i in range(lo, hi):
        if i >= len(cx) or np.isnan(cx[i]):
            continue
        ax, ay = adjust(float(cx[i]), float(cy[i]), i, h, w)
        pts.append((int(ax * w), int(ay * h), i))
    if len(pts) < 2:
        return

    for j in range(1, len(pts)):
        x0, y0, _ = pts[j - 1]
        x1, y1, fi = pts[j]
        alpha = j / len(pts)
        spd = float(speed_curve[fi]) if fi < len(speed_curve) else 1.0
        base = _speed_color(spd)
        col = tuple(int(c * (0.25 + 0.75 * alpha)) for c in base)
        thick = max(1, int(1 + alpha * 1.5))
        cv2.line(frame, (x0, y0), (x1, y1), col, thick, cv2.LINE_AA)

    x, y, _ = pts[-1]
    cv2.circle(frame, (x, y), 5, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 5, (60, 60, 60), 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Layer 4: Speed badge (lightweight, also used standalone)
# ---------------------------------------------------------------------------

def make_speed_badge_fn(
    speed_curve: np.ndarray,
) -> Callable[[np.ndarray, int, float], np.ndarray]:
    """Small rounded badge in top-right with current speed multiplier."""

    def badge(frame: np.ndarray, src_idx: int, speed: float) -> np.ndarray:
        h, w = frame.shape[:2]
        text = f"{speed:.1f}x"
        font = cv2.FONT_HERSHEY_SIMPLEX
        fs = max(0.55, h / 900)
        thick = max(1, int(h / 500))
        tw, th = cv2.getTextSize(text, font, fs, thick)[0]

        pad, margin = 8, 10
        bx1 = w - tw - pad * 2 - margin
        by1 = margin
        bx2 = w - margin
        by2 = margin + th + pad * 2

        _semi_rect(frame, (bx1, by1), (bx2, by2), (20, 20, 20), 0.65)
        color = _speed_color(speed)
        cv2.putText(frame, text, (bx1 + pad, by2 - pad),
                    font, fs, color, thick, cv2.LINE_AA)
        return frame

    return badge


# ---------------------------------------------------------------------------
# Layer 5: Frame counter + mode label
# ---------------------------------------------------------------------------

def _draw_frame_info(frame: np.ndarray, src_idx: int, fps: float,
                     h: int, w: int, mode: str = "progress",
                     time_map: np.ndarray | None = None) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = max(0.5, h / 900)
    small = fs * 0.65
    src_t = src_idx / fps if fps > 0 else 0
    tag = "PROG" if mode == "progress" else "ACT"

    # Include output time when time_map is available
    if time_map is not None and len(time_map) > 0 and src_idx < len(time_map):
        out_t = float(time_map[src_idx])
        text = f"f{src_idx} | {src_t:.1f}s \u2192 {out_t:.1f}s | {tag}"
    else:
        text = f"f{src_idx} | {src_t:.1f}s | {tag}"
    tw = cv2.getTextSize(text, font, small, 1)[0][0]

    _semi_rect(frame, (5, 5), (tw + 18, 35), (20, 20, 20), 0.65)
    cv2.putText(frame, text, (10, 28), font, small,
                (200, 200, 200), 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Layer 6: Rest badge
# ---------------------------------------------------------------------------

def _draw_rest_badge(frame: np.ndarray, h: int, w: int) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = max(0.45, h / 1100)
    thick = max(1, int(h / 600))
    text = "REST"
    tw, th = cv2.getTextSize(text, font, fs, thick)[0]

    cx = w // 2
    bx1, by1 = cx - tw // 2 - 8, 8
    bx2, by2 = cx + tw // 2 + 8, 8 + th + 10

    _semi_rect(frame, (bx1, by1), (bx2, by2), (60, 50, 120), 0.7)
    cv2.putText(frame, text, (bx1 + 8, by2 - 5), font, fs,
                (180, 170, 220), thick, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Layer 7: Score bars (pose + flow)
# ---------------------------------------------------------------------------

def _draw_score_bars(frame: np.ndarray, src_idx: int,
                     scores: np.ndarray, h: int, w: int,
                     flow_scores: np.ndarray | None,
                     bar_y_base: int) -> None:
    bar_h = max(3, int(h * 0.007))
    gap = 1
    font = cv2.FONT_HERSHEY_SIMPLEX
    label_fs = max(0.25, h / 3200)

    # Pose / movement score
    if src_idx < len(scores):
        s = float(scores[src_idx])
        y1 = bar_y_base - bar_h * 2 - gap
        y2 = y1 + bar_h
        if y1 >= 0:
            frame[y1:y2, :] = (25, 25, 25)
            bw = max(0, int(w * s))
            if bw > 0:
                g = int(170 * s + 40)
                frame[y1:y2, :bw] = (45, g, 65)
            cv2.putText(frame, "pose", (3, y2 - 1), font, label_fs,
                        (80, 80, 80), 1, cv2.LINE_AA)

    # Flow score
    if flow_scores is not None and src_idx < len(flow_scores):
        fv = float(flow_scores[src_idx])
        y1 = bar_y_base - bar_h
        y2 = y1 + bar_h
        if y1 >= 0:
            frame[y1:y2, :] = (25, 25, 25)
            bw = max(0, int(w * fv))
            if bw > 0:
                b = int(160 * fv + 40)
                frame[y1:y2, :bw] = (65, 110, b)
            cv2.putText(frame, "flow", (3, y2 - 1), font, label_fs,
                        (80, 80, 80), 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Layer 8: Timeline strip (pre-rendered, blitted per-frame)
# ---------------------------------------------------------------------------

_TIMELINE_W = 1200  # canonical width; resized to actual frame width


def _nice_tick(total_s: float) -> float:
    """Pick a round tick interval for the time axis."""
    for c in (0.5, 1, 2, 5, 10, 15, 30, 60):
        if total_s / c <= 15:
            return c
    return 60.0


def _prerender_timeline(
    speed_curve: np.ndarray,
    scores: np.ndarray,
    fps: float,
    rest_mask: np.ndarray | None,
    pins: list | None,
    flow_scores: np.ndarray | None,
    time_map: np.ndarray | None = None,
) -> np.ndarray:
    """Build a static timeline image (H x W x 3) at canonical width."""
    tw = _TIMELINE_W
    n = len(speed_curve)
    out_tick_h = 6  # height of the output-time tick lane
    strip_h = 40 + out_tick_h

    if n == 0:
        return np.full((strip_h, tw, 3), 20, dtype=np.uint8)

    speed_lane_h = 22
    divider = 2
    score_lane_h = 40 - speed_lane_h - divider  # keep original proportions
    img = np.full((strip_h, tw, 3), 20, dtype=np.uint8)

    # Map pixel columns → frame indices
    col_idx = np.linspace(0, n - 1, tw).astype(int)

    # ── speed lane (top) ──────────────────────────────────────────
    speeds = speed_curve[col_idx]
    smin = float(speed_curve.min())
    smax = float(speed_curve.max())
    t = (speeds - smin) / max(smax - smin, 1e-6)

    r = (np.clip(t * 2.2, 0, 1) * 190 + 35).astype(np.uint8)
    g = (np.clip(1.4 - t * 1.4, 0, 1) * 180 + 35).astype(np.uint8)
    b_arr = np.full(tw, 45, dtype=np.uint8)
    colors = np.stack([r, g, b_arr], axis=-1)               # (W, 3)

    bar_h = (t * speed_lane_h * 0.7 + speed_lane_h * 0.3).astype(int)
    rows = np.arange(speed_lane_h)[:, None]                  # (H, 1)
    tops = (speed_lane_h - bar_h)[None, :]                   # (1, W)
    mask = rows >= tops                                       # (H, W)

    lane = np.full((speed_lane_h, tw, 3), 20, dtype=np.uint8)
    cbroad = np.broadcast_to(colors[None, :, :], lane.shape).copy()
    lane[mask] = cbroad[mask]

    # Rest overlay — tint rest regions purple
    if rest_mask is not None and len(rest_mask) == n:
        rcols = rest_mask[col_idx]
        rmask2d = np.broadcast_to(rcols[None, :], (speed_lane_h, tw))
        both = mask & rmask2d
        if np.any(both):
            lane[both] = (
                lane[both].astype(np.float32) * 0.35
                + np.array([75, 65, 155], dtype=np.float32) * 0.65
            ).astype(np.uint8)

    img[:speed_lane_h] = lane

    # Thin divider line
    img[speed_lane_h:speed_lane_h + divider, :] = (35, 35, 35)

    # ── score lane (bottom) ───────────────────────────────────────
    sc_top = speed_lane_h + divider
    sv = scores[col_idx]
    sbh = np.clip((sv * score_lane_h).astype(int), 0, score_lane_h)
    srows = np.arange(score_lane_h)[:, None]
    stops = (score_lane_h - sbh)[None, :]
    smask = srows >= stops

    sg = (sv * 160 + 40).astype(np.uint8)
    sc_colors = np.stack([
        np.full(tw, 40, dtype=np.uint8),
        sg,
        np.full(tw, 55, dtype=np.uint8),
    ], axis=-1)

    sc_lane = np.full((score_lane_h, tw, 3), 20, dtype=np.uint8)
    sc_broad = np.broadcast_to(sc_colors[None, :, :], sc_lane.shape).copy()
    sc_lane[smask] = sc_broad[smask]

    # Flow overlay on score lane — blue tint
    if flow_scores is not None and len(flow_scores) == n:
        fv = flow_scores[col_idx]
        fbh = np.clip((fv * score_lane_h).astype(int), 0, score_lane_h)
        ftops = (score_lane_h - fbh)[None, :]
        fmask = srows >= ftops
        if np.any(fmask):
            sc_lane[fmask] = (
                sc_lane[fmask].astype(np.float32) * 0.55
                + np.array([75, 115, 200], dtype=np.float32) * 0.45
            ).astype(np.uint8)

    img[sc_top:sc_top + score_lane_h] = sc_lane

    # ── pin markers ───────────────────────────────────────────────
    if pins:
        for pin in pins:
            fi = int(pin[0] * fps)
            if 0 <= fi < n:
                px = int(fi * tw / n)
                cv2.drawMarker(
                    img, (px, speed_lane_h + 1), (255, 220, 80),
                    cv2.MARKER_DIAMOND, 6, 1, cv2.LINE_AA,
                )

    # ── source time ticks ──────────────────────────────────────────
    total = n / fps if fps > 0 else 0
    src_strip_bottom = speed_lane_h + divider + score_lane_h  # bottom of original lanes
    tick = _nice_tick(total)
    if tick > 0:
        for ts in np.arange(tick, total, tick):
            px = int(ts * fps * tw / n) if n > 0 else 0
            if 0 < px < tw:
                cv2.line(img, (px, 0), (px, 3), (80, 80, 80), 1)
                cv2.line(img, (px, src_strip_bottom - 3), (px, src_strip_bottom - 1),
                         (80, 80, 80), 1)

    # ── output time lane (bottom strip) ──────────────────────────
    out_lane_top = src_strip_bottom
    # Dark background for the output-time lane
    img[out_lane_top:out_lane_top + out_tick_h, :] = (15, 15, 15)
    # Thin separator line
    img[out_lane_top, :] = (45, 45, 45)

    if time_map is not None and len(time_map) == n:
        total_out = float(time_map[-1]) if n > 0 else 0.0
        if total_out > 0:
            # Draw output-time ticks at regular output-second intervals,
            # mapped back to their source-frame position on the timeline.
            out_tick_interval = _nice_tick(total_out)
            if out_tick_interval > 0:
                font = cv2.FONT_HERSHEY_SIMPLEX
                for ot in np.arange(out_tick_interval, total_out, out_tick_interval):
                    # Binary-search: find source frame where output time >= ot
                    src_fi = int(np.searchsorted(time_map, ot))
                    src_fi = min(src_fi, n - 1)
                    px = int(src_fi * tw / n)
                    if 0 < px < tw:
                        cv2.line(img, (px, out_lane_top + 1),
                                 (px, out_lane_top + out_tick_h - 1),
                                 (120, 180, 255), 1)
                        # Label every other tick to avoid clutter
                        label = f"{ot:.0f}" if ot == int(ot) else f"{ot:.1f}"
                        lw = cv2.getTextSize(label, font, 0.22, 1)[0][0]
                        lx = min(px + 2, tw - lw - 2)
                        cv2.putText(img, label,
                                    (lx, out_lane_top + out_tick_h - 1),
                                    font, 0.22, (100, 150, 220), 1, cv2.LINE_AA)

            # Label on the right: total output duration
            font = cv2.FONT_HERSHEY_SIMPLEX
            dur_label = f">{total_out:.0f}s" if total_out == int(total_out) else f">{total_out:.1f}s"
            dlw = cv2.getTextSize(dur_label, font, 0.25, 1)[0][0]
            cv2.putText(img, dur_label, (tw - dlw - 4, out_lane_top + out_tick_h - 1),
                        font, 0.25, (120, 180, 255), 1, cv2.LINE_AA)

    return img


def _blit_timeline(frame: np.ndarray, tl_resized: np.ndarray,
                   src_idx: int, n_frames: int,
                   h: int, w: int, strip_h: int,
                   time_map: np.ndarray | None = None,
                   total_output_duration: float = 0.0) -> None:
    """Composite the pre-resized timeline and draw both playheads."""
    y1 = h - strip_h
    region = frame[y1:h, :w]
    cv2.addWeighted(tl_resized, 0.88, region, 0.12, 0, region)
    frame[y1:h, :w] = region

    if n_frames > 0:
        # Source playhead — white
        px = max(0, min(int(src_idx * w / n_frames), w - 1))
        cv2.line(frame, (px, y1), (px, h), (255, 255, 255), 1, cv2.LINE_AA)
        tri = np.array([[px - 3, y1], [px + 3, y1], [px, y1 + 4]])
        cv2.fillPoly(frame, [tri], (255, 255, 255))

        # Output playhead — cyan/blue, shows where we are in output time
        if (time_map is not None and len(time_map) > 0
                and total_output_duration > 0 and src_idx < len(time_map)):
            out_frac = float(time_map[src_idx]) / total_output_duration
            out_px = max(0, min(int(out_frac * w), w - 1))
            out_color = (255, 180, 80)  # light cyan-ish (BGR: light blue)
            cv2.line(frame, (out_px, y1), (out_px, h),
                     out_color, 1, cv2.LINE_AA)
            # Upward triangle at bottom edge
            tri_out = np.array([
                [out_px - 3, h], [out_px + 3, h], [out_px, h - 4],
            ])
            cv2.fillPoly(frame, [tri_out], out_color)


# ---------------------------------------------------------------------------
# Layer 9: Stabilization inset
# ---------------------------------------------------------------------------

_STAB_W, _STAB_H = 170, 48


def _prerender_stab(
    dx: np.ndarray, dy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Pre-render a mini plot of stabilization offset magnitude."""
    mag = np.sqrt(dx ** 2 + dy ** 2)
    n = len(dx)
    iw, ih = _STAB_W, _STAB_H
    img = np.full((ih, iw, 3), 15, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (iw - 1, ih - 1), (45, 45, 45), 1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "stab offset", (4, 11), font, 0.28,
                (100, 100, 100), 1, cv2.LINE_AA)

    if n < 2:
        return img, mag

    mx = max(float(np.percentile(mag, 99)), 1e-6)
    n_cols = iw - 12
    cols = np.linspace(0, n - 1, n_cols).astype(int)
    vals = mag[cols]
    ys = (ih - 5 - (vals / mx) * (ih - 18)).astype(int)
    ys = np.clip(ys, 14, ih - 4)
    xs = np.arange(6, 6 + n_cols)[:len(ys)]
    pts = np.stack([xs, ys], axis=-1).astype(np.int32)
    cv2.polylines(img, [pts], False, (140, 185, 255), 1, cv2.LINE_AA)

    return img, mag


def _blit_stab(frame: np.ndarray, stab_img: np.ndarray,
               stab_mag: np.ndarray, src_idx: int,
               h: int, w: int, tl_strip_h: int) -> None:
    """Overlay the stabilization inset above the timeline."""
    ih, iw = stab_img.shape[:2]
    margin = 8
    x1 = w - iw - margin
    y1 = h - tl_strip_h - ih - margin - 14      # above score bars
    if y1 < 0 or x1 < 0:
        return
    x2, y2 = x1 + iw, y1 + ih

    ov = frame[y1:y2, x1:x2].copy()
    cv2.addWeighted(stab_img, 0.82, ov, 0.18, 0, frame[y1:y2, x1:x2])

    # Playhead inside inset
    n = len(stab_mag)
    if n > 1:
        n_cols = iw - 12
        px_local = int(src_idx * n_cols / n) + 6
        px_local = max(6, min(px_local, iw - 7))
        cv2.line(frame, (x1 + px_local, y1 + 13),
                 (x1 + px_local, y2 - 3), (255, 255, 255), 1)

    # Current offset value
    if 0 <= src_idx < n:
        pct = float(stab_mag[src_idx]) * 100
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"{pct:.1f}%", (x1 + 4, y1 - 3),
                    font, 0.32, (140, 185, 255), 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Public: full debug overlay factory
# ---------------------------------------------------------------------------

def make_debug_overlay_fn(
    poses: list,
    scores: np.ndarray,
    speed_curve: np.ndarray,
    fps: float,
    *,
    flow_scores: np.ndarray | None = None,
    tracks: list | None = None,
    stab_offsets: tuple[np.ndarray, np.ndarray] | None = None,
    stabilize_crop: float = 0.0,
    rest_mask: np.ndarray | None = None,
    pins: list | None = None,
    mode: str = "progress",
) -> Callable[[np.ndarray, int, float], np.ndarray]:
    """Create the full debug overlay function.

    Pre-computes all static visuals (timeline, stab inset, COM trail
    positions) once. The returned callable draws everything per frame.

    When stab_offsets and stabilize_crop are provided, all body-space
    coordinates (skeleton, bbox, COM trail) are remapped from the
    original [0,1] frame to the stabilization-cropped frame.
    """
    badge_fn = make_speed_badge_fn(speed_curve)

    # Pre-compute output time mapping for the speed transformation tracker
    time_map = get_time_mapping(speed_curve, fps) if len(speed_curve) > 0 else np.array([])
    total_output_duration = float(time_map[-1]) if len(time_map) > 0 else 0.0

    # Pre-compute center-of-mass trail
    com_x, com_y = _compute_com(poses)

    # Pre-render timeline
    timeline_base = _prerender_timeline(
        speed_curve, scores, fps,
        rest_mask=rest_mask,
        pins=pins,
        flow_scores=flow_scores,
        time_map=time_map,
    )

    # Pre-render stabilization inset
    stab_img: np.ndarray | None = None
    stab_mag: np.ndarray | None = None
    if stab_offsets is not None:
        stab_img, stab_mag = _prerender_stab(*stab_offsets)

    # Coordinate adjuster for stabilization crop
    _adjust: Callable | None = None
    if stab_offsets is not None and stabilize_crop > 0:
        _adjust = _stab_coord_adjuster(stab_offsets, stabilize_crop)

    n_frames = len(speed_curve)

    # Cache resized timeline per output resolution (constant within a render)
    _tl_cache: dict[tuple[int, int], np.ndarray] = {}

    def _adjusted_pose(pose, src_idx: int, h: int, w: int):
        """Remap pose landmarks to cropped-frame coordinates."""
        if _adjust is None or pose is None:
            return pose
        if isinstance(pose, dict):
            return {
                name: (_adjust(x, y, src_idx, h, w) + (vis,))
                for name, (x, y, vis) in pose.items()
            }
        return pose

    def _adjusted_track(track, src_idx: int, h: int, w: int):
        """Remap tracking bbox to cropped-frame coordinates."""
        if _adjust is None or track is None:
            return track
        bn = track.get("bbox_norm")
        if bn is None:
            return track
        x1, y1, x2, y2 = bn
        ax1, ay1 = _adjust(x1, y1, src_idx, h, w)
        ax2, ay2 = _adjust(x2, y2, src_idx, h, w)
        return {**track, "bbox_norm": (ax1, ay1, ax2, ay2)}

    def _adjusted_com(cx_arr, cy_arr, idx: int, h: int, w: int):
        """Remap a single COM point to cropped-frame coordinates."""
        if _adjust is None:
            return float(cx_arr[idx]), float(cy_arr[idx])
        return _adjust(float(cx_arr[idx]), float(cy_arr[idx]), idx, h, w)

    def overlay(frame: np.ndarray, src_idx: int, speed: float) -> np.ndarray:
        h, w = frame.shape[:2]
        strip_h = max(24, int(h * 0.055))

        # Resize timeline once per resolution
        key = (w, strip_h)
        if key not in _tl_cache:
            _tl_cache[key] = cv2.resize(
                timeline_base, (w, strip_h),
                interpolation=cv2.INTER_LINEAR,
            )
        tl = _tl_cache[key]

        # ── body layers (with stabilization coordinate adjustment) ──
        if tracks is not None and src_idx < len(tracks):
            _draw_tracking_bbox(frame, _adjusted_track(tracks[src_idx], src_idx, h, w), h, w)

        if src_idx < len(poses) and poses[src_idx] is not None:
            _draw_skeleton(frame, _adjusted_pose(poses[src_idx], src_idx, h, w), h, w)

        if _adjust is not None:
            _draw_com_trail_adjusted(
                frame, com_x, com_y, src_idx, h, w,
                speed_curve, _adjust,
            )
        else:
            _draw_com_trail(frame, com_x, com_y, src_idx, h, w, speed_curve)

        # ── top bar ──
        frame = badge_fn(frame, src_idx, speed)
        _draw_frame_info(frame, src_idx, fps, h, w, mode, time_map=time_map)

        if rest_mask is not None and src_idx < len(rest_mask) and rest_mask[src_idx]:
            _draw_rest_badge(frame, h, w)

        # ── bottom layers ──
        _blit_timeline(frame, tl, src_idx, n_frames, h, w, strip_h,
                       time_map=time_map, total_output_duration=total_output_duration)

        bar_base = h - strip_h - 2
        _draw_score_bars(frame, src_idx, scores, h, w,
                         flow_scores=flow_scores, bar_y_base=bar_base)

        if stab_img is not None and stab_mag is not None:
            _blit_stab(frame, stab_img, stab_mag, src_idx, h, w, strip_h)

        return frame

    return overlay


# Backward compat alias
make_overlay_fn = make_debug_overlay_fn
