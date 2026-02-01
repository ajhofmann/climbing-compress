"""Analysis result caching — skip re-analysis when tuning parameters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


def _video_hash(video_path: str) -> str:
    """Fast hash based on file path, size, and mtime."""
    p = Path(video_path)
    stat = p.stat()
    key = f"{p.name}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def get_cache_path(video_path: str) -> Path:
    """Return cache directory for a video."""
    h = _video_hash(video_path)
    path = CACHE_DIR / h
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_analysis(video_path: str, poses: list, fps: float, scores: np.ndarray):
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
        json.dump({"fps": fps, "poses": serializable}, f)

    np.save(cache / "scores.npy", scores)


def load_analysis(video_path: str) -> tuple | None:
    """Load cached poses, fps, and scores. Returns None if no cache."""
    cache = get_cache_path(video_path)
    poses_path = cache / "poses.json"
    scores_path = cache / "scores.npy"

    if not poses_path.exists() or not scores_path.exists():
        return None

    with open(poses_path) as f:
        data = json.load(f)

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
