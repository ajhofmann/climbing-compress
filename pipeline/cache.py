"""Analysis result caching — skip re-analysis when tuning parameters.

Caches pose data, movement scores, tracking data, and flow scores
under content-hash-based directories.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


def content_hash(video_path: str) -> str:
    """Content-based hash from file size + head/tail bytes.

    Stable across renames and re-uploads — same content always gets
    the same hash, so pose cache survives across dev iterations.
    """
    p = Path(video_path)
    size = p.stat().st_size
    chunk = 65536  # 64KB

    h = hashlib.md5()
    h.update(str(size).encode())

    with open(p, "rb") as f:
        h.update(f.read(chunk))
        if size > chunk * 2:
            f.seek(-chunk, 2)
            h.update(f.read(chunk))

    return h.hexdigest()[:12]


def get_cache_path(video_path: str) -> Path:
    """Return cache directory for a video."""
    h = content_hash(video_path)
    path = CACHE_DIR / h
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_analysis(video_path: str, poses: list, fps: float, scores: np.ndarray, stride: int = 1):
    """Save poses and scores to cache."""
    cache = get_cache_path(video_path)

    # Convert poses to a serializable format
    # Each pose is either None or dict of name -> (x, y, vis)
    serializable = []
    for p in poses:
        if p is None:
            serializable.append(None)
        else:
            serializable.append({k: list(v) for k, v in p.items()})

    with open(cache / "poses.json", "w") as f:
        json.dump({"fps": fps, "stride": stride, "poses": serializable}, f)

    np.save(cache / "scores.npy", scores)


def load_analysis(video_path: str, expected_stride: int | None = None) -> tuple | None:
    """Load cached poses, fps, and scores. Returns None if no cache.

    If expected_stride is given, returns None on mismatch so the caller
    re-runs pose extraction at the new stride.
    """
    cache = get_cache_path(video_path)
    poses_path = cache / "poses.json"
    scores_path = cache / "scores.npy"

    if not poses_path.exists() or not scores_path.exists():
        return None

    with open(poses_path) as f:
        data = json.load(f)

    # Stride mismatch → treat as cache miss
    if expected_stride is not None and data.get("stride", 2) != expected_stride:
        return None

    fps = data["fps"]
    poses = []
    for p in data["poses"]:
        if p is None:
            poses.append(None)
        else:
            poses.append({k: tuple(v) for k, v in p.items()})

    scores = np.load(scores_path)
    return poses, fps, scores


# ---- Tracker cache ----

def save_tracks(video_path: str, tracks: list[dict | None], fps: float, stride: int = 1):
    """Save per-frame tracking results to cache."""
    cache = get_cache_path(video_path)

    serializable = []
    for t in tracks:
        if t is None:
            serializable.append(None)
        else:
            # Only cache the fields we need (bbox_norm, track_id, confidence)
            serializable.append({
                "bbox_norm": list(t["bbox_norm"]) if "bbox_norm" in t else None,
                "track_id": t.get("track_id"),
                "confidence": t.get("confidence"),
                "n_persons": t.get("n_persons", 1),
            })

    with open(cache / "tracks.json", "w") as f:
        json.dump({"fps": fps, "stride": stride, "tracks": serializable}, f)


def load_tracks(video_path: str, expected_stride: int | None = None) -> tuple | None:
    """Load cached tracking results. Returns (tracks, fps) or None."""
    cache = get_cache_path(video_path)
    tracks_path = cache / "tracks.json"

    if not tracks_path.exists():
        return None

    with open(tracks_path) as f:
        data = json.load(f)

    if expected_stride is not None and data.get("stride", 1) != expected_stride:
        return None

    fps = data["fps"]
    tracks = []
    for t in data["tracks"]:
        if t is None:
            tracks.append(None)
        else:
            if t.get("bbox_norm") is not None:
                t["bbox_norm"] = tuple(t["bbox_norm"])
            tracks.append(t)

    return tracks, fps


def has_tracks(video_path: str) -> bool:
    """Check if tracking cache exists for a video."""
    cache = get_cache_path(video_path)
    return (cache / "tracks.json").exists()


# ---- Flow scores cache ----

def save_flow_scores(video_path: str, flow_scores: np.ndarray):
    """Save flow-based movement scores to cache."""
    cache = get_cache_path(video_path)
    np.save(cache / "flow_scores.npy", flow_scores)


def load_flow_scores(video_path: str) -> np.ndarray | None:
    """Load cached flow scores. Returns None if no cache."""
    cache = get_cache_path(video_path)
    path = cache / "flow_scores.npy"
    if not path.exists():
        return None
    return np.load(path)


# ---- Raw anchor trajectory cache (for stabilization) ----

def save_raw_anchor(video_path: str, ax: np.ndarray, ay: np.ndarray):
    """Save pre-smoothing anchor trajectory for stabilization."""
    cache = get_cache_path(video_path)
    np.save(cache / "raw_anchor_x.npy", ax)
    np.save(cache / "raw_anchor_y.npy", ay)


def load_raw_anchor(video_path: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Load cached raw anchor trajectory. Returns (ax, ay) or None."""
    cache = get_cache_path(video_path)
    ax_path = cache / "raw_anchor_x.npy"
    ay_path = cache / "raw_anchor_y.npy"
    if not ax_path.exists() or not ay_path.exists():
        return None
    return np.load(ax_path), np.load(ay_path)


# ---- Camera motion cache ----

def save_camera_motion(video_path: str, cam_dx: np.ndarray, cam_dy: np.ndarray):
    """Save per-frame camera motion estimates to cache."""
    cache = get_cache_path(video_path)
    np.save(cache / "cam_dx.npy", cam_dx)
    np.save(cache / "cam_dy.npy", cam_dy)


def load_camera_motion(video_path: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Load cached camera motion. Returns (cam_dx, cam_dy) or None."""
    cache = get_cache_path(video_path)
    dx_path = cache / "cam_dx.npy"
    dy_path = cache / "cam_dy.npy"
    if not dx_path.exists() or not dy_path.exists():
        return None
    return np.load(dx_path), np.load(dy_path)


# ---- General ----

def has_cache(video_path: str) -> bool:
    """Check if analysis cache exists for a video."""
    cache = get_cache_path(video_path)
    return (cache / "poses.json").exists() and (cache / "scores.npy").exists()


def clear_cache(video_path: str):
    """Remove all cache for a video."""
    cache = get_cache_path(video_path)
    if cache.exists():
        for f in cache.iterdir():
            f.unlink()
