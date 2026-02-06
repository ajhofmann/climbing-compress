"""FastAPI backend for climb-ramp — thin HTTP layer.

All pipeline orchestration lives in ``pipeline.orchestrate``.
SSE streaming is handled by ``utils.sse``.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import shutil
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline.cache import (
    load_analysis, has_cache, content_hash, load_flow_scores,
    load_camera_motion,
)
from pipeline.orchestrate import (
    run_analysis, run_render, compute_scores_and_curve, curve_stats,
)
from pipeline.speed_curve import detect_rest
from utils.sse import sse_response
from utils.video_io import get_video_info
from utils.viz import generate_thumbnails
from db import (
    init_db,
    sync_input_dir,
    get_video,
    list_videos as db_list_videos,
    get_video_by_hash,
    register_video,
    update_video_info,
)

logger = logging.getLogger(__name__)

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "data/input"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data/output"))
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

init_db()
sync_input_dir(INPUT_DIR)

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="climb-ramp")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----

class Pin(BaseModel):
    time: float
    speed: float
    radius: float = 2.0  # influence radius in seconds

class SolveRequest(BaseModel):
    video_id: str
    mode: str = "progress"
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

class RenderRequest(SolveRequest):
    scale: float = 0.5
    output_fps: float = 30
    crf: int = 23
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

class AnalyzeRequest(BaseModel):
    video_id: str
    stride: int = 1
    force: bool = False
    use_tracker: bool = True
    use_flow: bool = True
    tracker_model: str = "yolo26m"


# ---- Helpers ----

def _get_video_path(video_id: str) -> Path:
    record = get_video(video_id)
    if not record:
        raise HTTPException(404, f"Video '{video_id}' not found")
    path = Path(record["path"])
    if not path.exists():
        raise HTTPException(404, f"Video '{video_id}' not found")
    return path


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


# ---- Endpoints ----

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix or ".mov"

    # Save to temp first so we can hash before committing
    tmp = INPUT_DIR / f"_tmp_{uuid.uuid4().hex[:8]}{ext}"
    try:
        with open(tmp, "wb") as f:
            shutil.copyfileobj(file.file, f)

        ch = content_hash(str(tmp))

        # Reuse existing file if same content already in input dir
        existing = get_video_by_hash(ch)
        if existing:
            existing_id = existing["id"]
            existing_path = Path(existing["path"])
            if existing_path.exists():
                tmp.unlink()
                info = (
                    json.loads(existing["info_json"])
                    if existing.get("info_json")
                    else get_video_info(str(existing_path))
                )
                if not existing.get("info_json"):
                    update_video_info(existing_id, info)
                thumbs = generate_thumbnails(str(existing_path), n=8)
                return {
                    "video_id": existing_id,
                    "info": info,
                    "thumbnails": _encode_thumbnails(thumbs),
                    "cached": has_cache(str(existing_path)),
                    "reused": True,
                }

        # New video — rename temp to final
        video_id = uuid.uuid4().hex[:10]
        dest = INPUT_DIR / f"{video_id}{ext}"
        tmp.rename(dest)

        info = get_video_info(str(dest))
        thumbs = generate_thumbnails(str(dest), n=8)
        register_video(video_id, dest.name, str(dest), ch, info=info)

        return {
            "video_id": video_id,
            "info": info,
            "thumbnails": _encode_thumbnails(thumbs),
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
    result = []
    for record in db_list_videos():
        path = Path(record["path"])
        if not path.exists():
            continue
        if record.get("info_json"):
            info = json.loads(record["info_json"])
        else:
            info = get_video_info(str(path))
            update_video_info(record["id"], info)
        result.append({"video_id": record["id"], "filename": record["filename"], "info": info})
    return result


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

    stats = curve_stats(curve, fps)

    return {
        "curve": curve_ds,
        "times": times_ds,
        "scores": scores_ds,
        "rest_regions": rest_regions,
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
