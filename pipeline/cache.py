"""Analysis result caching — skip re-analysis when tuning parameters."""

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


# Internal alias
_video_hash = content_hash


def get_cache_path(video_path: str) -> Path:
    """Return cache directory for a video."""
    h = _video_hash(video_path)
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


def has_cache(video_path: str) -> bool:
    """Check if analysis cache exists for a video."""
    cache = get_cache_path(video_path)
    return (cache / "poses.json").exists() and (cache / "scores.npy").exists()


def clear_cache(video_path: str):
    """Remove cache for a video."""
    cache = get_cache_path(video_path)
    for f in cache.iterdir():
        f.unlink()
