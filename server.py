"""FastAPI backend for climb-ramp — thin HTTP layer.

All pipeline orchestration lives in ``pipeline.orchestrate``.
SSE streaming is handled by ``utils.sse``.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import shutil
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from pipeline.cache import (
    load_analysis, has_cache, content_hash, load_flow_scores,
    load_camera_motion,
)
from pipeline.orchestrate import (
    run_analysis, run_render, compute_scores_and_curve, curve_stats, detect_crux_points,
)
from pipeline.speed_curve import detect_rest
from utils.sse import sse_response
from utils.video_io import get_video_info
from utils.viz import generate_thumbnails

logger = logging.getLogger(__name__)

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "data/input"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data/output"))
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "512"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_VIDEO_EXTS = (".mov", ".mp4", ".avi", ".mkv")

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="climb-ramp")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for video paths by ID
_videos: dict[str, Path] = {}

# Content-hash index for upload dedup (hash -> video_id)
_file_hashes: dict[str, str] = {}
# Video metadata cache (info + thumbnails) for fast local reloads
_video_meta_cache: dict[str, dict[str, object]] = {}

# Scan existing input videos on startup
for _f in INPUT_DIR.iterdir():
    if _f.suffix.lower() in ALLOWED_VIDEO_EXTS and not _f.name.startswith("_tmp_"):
        _videos[_f.stem] = _f
        try:
            _file_hashes[content_hash(str(_f))] = _f.stem
        except (OSError, ValueError) as exc:
            logger.warning("Failed to hash %s: %s", _f, exc)


# ---- Models ----

class Pin(BaseModel):
    time: float
    speed: float
    radius: float = 2.0  # influence radius in seconds

class Keyframe(BaseModel):
    time: float
    speed: float

class SolveRequest(BaseModel):
    video_id: str
    mode: str = "progress"
    edit_mode: str = "pins"
    progress_action_blend: float = Field(default=0.5, ge=0.0, le=1.0)
    target_duration: float = 15
    sensitivity: float = 0.35
    max_speed: float = 10
    min_speed: float = 0.25
    steepness: float = 14
    smoothing: float = 0.3
    hand_weight: float = 2.0
    foot_weight: float = 1.0
    core_weight: float = 3.0
    progress_floor: float = 0.02
    vertical_bias: float = 0.7
    down_weight: float = 0.15
    rest_threshold_s: float = 0.3
    trim_start: float = 0.0
    trim_end: float = 0.0
    pins: list[Pin] = []
    keyframes: list[Keyframe] = []

class RenderRequest(SolveRequest):
    scale: float = 0.5
    output_fps: float = 30
    crf: int = 23
    output_aspect: str = "original"
    auto_reframe: bool = False
    debug_overlay: bool = True
    include_audio: bool = True
    # Pose-anchored stabilization
    stabilize: bool = False
    stabilize_strength: float = 0.7
    stabilize_smoothness: float = 0.8
    stabilize_crop: float = 0.15
    # Feature-based stabilization (blend with pose-anchored)
    use_feature_stabilize: bool = True
    feature_stabilize_weight: float = 0.5
    # Comparison: also render a uniform-speed version
    render_comparison: bool = False
    # Chapter card overlays
    render_chapters: bool = False

class AnalyzeRequest(BaseModel):
    video_id: str
    stride: int = 1
    force: bool = False
    use_tracker: bool = True
    use_flow: bool = True
    tracker_model: str = "yolo26m"


# ---- Helpers ----

def _get_video_path(video_id: str) -> Path:
    if video_id not in _videos:
        raise HTTPException(404, f"Video '{video_id}' not found")
    return _videos[video_id]


def _encode_thumbnails(thumbs: list[np.ndarray]) -> list[str]:
    """Encode thumbnail arrays as base64 data URLs."""
    from PIL import Image
    urls = []
    for t in thumbs:
        img = Image.fromarray(t)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
        urls.append(f"data:image/jpeg;base64,{b64}")
    return urls


def _get_video_info_cached(video_id: str, path: Path) -> dict:
    entry = _video_meta_cache.get(video_id)
    if entry:
        info = entry.get("info")
        if isinstance(info, dict):
            return info
    info = get_video_info(str(path))
    _video_meta_cache.setdefault(video_id, {})["info"] = info
    return info


def _get_thumbnails_cached(video_id: str, path: Path, n: int = 8) -> list[str]:
    entry = _video_meta_cache.get(video_id)
    if entry:
        thumbs = entry.get("thumbnails")
        if isinstance(thumbs, list):
            return thumbs
    thumbs = _encode_thumbnails(generate_thumbnails(str(path), n=n))
    _video_meta_cache.setdefault(video_id, {})["thumbnails"] = thumbs
    return thumbs


# ---- Endpoints ----

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = Path(filename).suffix.lower() or ".mov"
    if ext not in ALLOWED_VIDEO_EXTS:
        allowed = ", ".join(ALLOWED_VIDEO_EXTS)
        raise HTTPException(415, f"Unsupported video format. Allowed: {allowed}")

    # Save to temp first so we can hash before committing
    tmp = INPUT_DIR / f"_tmp_{uuid.uuid4().hex[:8]}{ext}"
    try:
        with open(tmp, "wb") as f:
            shutil.copyfileobj(file.file, f)

        if MAX_UPLOAD_BYTES > 0 and tmp.stat().st_size > MAX_UPLOAD_BYTES:
            tmp.unlink()
            raise HTTPException(413, f"Upload too large (limit {MAX_UPLOAD_MB} MB)")

        ch = content_hash(str(tmp))

        # Reuse existing file if same content already in input dir
        if ch in _file_hashes:
            existing_id = _file_hashes[ch]
            if existing_id in _videos and _videos[existing_id].exists():
                tmp.unlink()
                dest = _videos[existing_id]
                info = _get_video_info_cached(existing_id, dest)
                thumbs = _get_thumbnails_cached(existing_id, dest, n=8)
                return {
                    "video_id": existing_id,
                    "info": info,
                    "thumbnails": thumbs,
                    "cached": has_cache(str(dest)),
                    "reused": True,
                }

        # New video — rename temp to final
        video_id = uuid.uuid4().hex[:10]
        dest = INPUT_DIR / f"{video_id}{ext}"
        tmp.rename(dest)

        _videos[video_id] = dest
        _file_hashes[ch] = video_id
        info = get_video_info(str(dest))
        thumbs = _encode_thumbnails(generate_thumbnails(str(dest), n=8))
        _video_meta_cache[video_id] = {"info": info, "thumbnails": thumbs}

        return {
            "video_id": video_id,
            "info": info,
            "thumbnails": thumbs,
            "cached": has_cache(str(dest)),
            "reused": False,
        }
    except (OSError, ValueError) as exc:
        if tmp.exists():
            tmp.unlink()
        logger.error("Upload failed: %s", exc)
        raise HTTPException(500, f"Upload failed: {exc}") from exc


@app.get("/api/videos")
async def list_videos():
    """List available input videos."""
    def _sort_key(item: tuple[str, Path]) -> tuple[float, str]:
        vid, path = item
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (-mtime, vid)

    result = []
    for vid, path in sorted(_videos.items(), key=_sort_key):
        try:
            info = _get_video_info_cached(vid, path)
        except (OSError, ValueError) as exc:
            logger.warning("Skipping unreadable video %s: %s", path, exc)
            continue
        result.append({
            "video_id": vid,
            "filename": path.name,
            "info": info,
            "cached": has_cache(str(path)),
        })
    return result


@app.get("/api/video-meta/{video_id}")
async def video_meta(video_id: str):
    """Fetch info + thumbnails for an already-uploaded source video."""
    path = _get_video_path(video_id)
    info = _get_video_info_cached(video_id, path)
    thumbs = _get_thumbnails_cached(video_id, path, n=8)
    return {
        "video_id": video_id,
        "info": info,
        "thumbnails": thumbs,
        "cached": has_cache(str(path)),
    }


@app.post("/api/analyze")
async def analyze_video(req: AnalyzeRequest):
    path = _get_video_path(req.video_id)

    def worker(emit):
        run_analysis(str(path), req, emit)

    return sse_response(worker)


@app.post("/api/solve")
async def solve_curve(req: SolveRequest):
    path = _get_video_path(req.video_id)
    cached = load_analysis(str(path))
    if not cached:
        raise HTTPException(400, "Run analyze first")

    poses, fps, _ = cached
    flow_scores = load_flow_scores(str(path))
    camera_motion = load_camera_motion(str(path))
    scores, curve, trimmed, start_frame = compute_scores_and_curve(
        req, poses, fps, flow_scores=flow_scores, camera_motion=camera_motion,
    )

    # Downsample curve for transfer — times are absolute (offset by trim start)
    n = len(curve)
    step = max(1, n // 500)
    curve_ds = curve[::step].tolist()
    trim_offset = start_frame / fps if fps > 0 else 0
    times_ds = ((np.arange(0, n, step) / fps) + trim_offset).tolist()

    # Downsample scores at the same rate as the curve
    scores_ds = scores[::step].tolist()

    # Rest detection (lightweight, scores-only) for debug visualization
    rest_mask = detect_rest(scores, fps, req.rest_threshold_s)
    rest_regions: list[list[float]] = []
    changes = np.diff(rest_mask.astype(np.int8), prepend=0, append=0)
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    for s, e in zip(starts, ends):
        t0 = float(s) / fps + trim_offset
        t1 = float(e) / fps + trim_offset
        rest_regions.append([round(t0, 2), round(t1, 2)])

    crux_points = []
    for fi, score in detect_crux_points(scores, fps):
        t = float(fi) / fps + trim_offset
        crux_points.append({
            "time": round(t, 2),
            "score": round(float(score), 3),
        })

    stats = curve_stats(curve, fps)

    return {
        "curve": curve_ds,
        "times": times_ds,
        "scores": scores_ds,
        "rest_regions": rest_regions,
        "crux_points": crux_points,
        "stats": stats,
    }


@app.post("/api/render")
async def render_video_endpoint(req: RenderRequest):
    path = _get_video_path(req.video_id)

    def worker(emit):
        run_render(str(path), req, OUTPUT_DIR, emit)

    return sse_response(worker)


@app.get("/api/video/{video_id}")
async def serve_video(video_id: str):
    # Check output first, then input
    for d in [OUTPUT_DIR, INPUT_DIR]:
        for f in d.iterdir():
            if f.stem == video_id:
                return FileResponse(str(f), media_type="video/mp4")
    raise HTTPException(404, "Video not found")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
