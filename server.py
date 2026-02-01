"""FastAPI backend for climb-ramp."""

from __future__ import annotations

import base64
import io
import json
import shutil
import time
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from pipeline.pose import extract_poses, interpolate_missing_poses
from pipeline.movement import score_movement, score_progress
from pipeline.speed_curve import (
    solve_speed_curve, solve_constant_progress, get_output_duration,
)
from pipeline.render import render_preview
from pipeline.stabilize import compute_stabilization_offsets, stabilization_stats
from pipeline.cache import save_analysis, load_analysis, has_cache, content_hash
from pipeline.debug_overlay import make_speed_badge_fn, make_debug_overlay_fn
from utils.video_io import get_video_info
from utils.viz import generate_thumbnails, render_waveform_data_url

INPUT_DIR = Path("data/input")
OUTPUT_DIR = Path("data/output")
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="climb-ramp")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for video paths by ID
_videos: dict[str, Path] = {}

# Content-hash index for upload dedup (hash -> video_id)
_file_hashes: dict[str, str] = {}

# Scan existing input videos on startup
for _f in INPUT_DIR.iterdir():
    if _f.suffix.lower() in (".mov", ".mp4", ".avi", ".mkv") and not _f.name.startswith("_tmp_"):
        _videos[_f.stem] = _f
        try:
            _file_hashes[content_hash(str(_f))] = _f.stem
        except Exception:
            pass


# ---- Models ----

class Pin(BaseModel):
    time: float
    speed: float

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
    trim_start: float = 0.0
    trim_end: float = 0.0
    pins: list[Pin] = []

class RenderRequest(BaseModel):
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
    trim_start: float = 0.0
    trim_end: float = 0.0
    pins: list[Pin] = []
    scale: float = 0.5
    output_fps: float = 30
    crf: int = 23
    debug_overlay: bool = True
    # Pose-anchored stabilization
    stabilize: bool = False
    stabilize_strength: float = 0.7
    stabilize_smoothness: float = 0.8
    stabilize_crop: float = 0.15

class AnalyzeRequest(BaseModel):
    video_id: str
    stride: int = 1
    force: bool = False


# ---- Helpers ----

def _get_video_path(video_id: str) -> Path:
    if video_id not in _videos:
        raise HTTPException(404, f"Video '{video_id}' not found")
    return _videos[video_id]


def _trim_poses(poses, fps, trim_start: float, trim_end: float):
    """Slice poses to the trimmed frame range. Returns (trimmed_poses, start_frame)."""
    n = len(poses)
    duration = n / fps if fps > 0 else 0

    start_f = int(trim_start * fps) if trim_start > 0 else 0
    end_f = int(trim_end * fps) if trim_end > 0 else n
    start_f = max(0, min(start_f, n))
    end_f = max(start_f, min(end_f, n))

    return poses[start_f:end_f], start_f


def _compute_scores_and_curve(req: SolveRequest, poses, fps):
    # Trim poses to selected range
    trimmed, start_frame = _trim_poses(poses, fps, req.trim_start, req.trim_end)

    # Offset pins into trimmed-region time and filter out-of-range
    trim_s = start_frame / fps if fps > 0 else 0
    trim_dur = len(trimmed) / fps if fps > 0 else 0
    pins = [
        (p.time - trim_s, p.speed) for p in req.pins
        if trim_s <= p.time <= trim_s + trim_dur
    ]

    if req.mode == "progress":
        scores = score_progress(trimmed, fps, smooth_sigma_s=req.smoothing)
        curve = solve_constant_progress(
            scores, fps,
            target_duration=req.target_duration,
            min_speed=req.min_speed,
            max_speed=req.max_speed,
            smoothing=req.smoothing,
            floor=req.progress_floor,
            pins=pins,
        )
    else:
        scores = score_movement(
            trimmed, fps,
            smooth_sigma_s=req.smoothing,
            hand_weight=req.hand_weight,
            foot_weight=req.foot_weight,
            core_weight=req.core_weight,
        )
        curve = solve_speed_curve(
            scores, fps,
            target_duration=req.target_duration,
            min_speed=req.min_speed,
            max_speed=req.max_speed,
            sensitivity=req.sensitivity,
            steepness=req.steepness,
            pins=pins,
        )

    return scores, curve, trimmed, start_frame


def _curve_stats(curve, fps):
    actual = get_output_duration(curve, fps)
    dt = 1.0 / fps
    slow_pct = float(np.sum(curve < 1.5) / len(curve) * 100)
    out_per = dt / curve
    si = np.argsort(curve)
    q = len(curve) // 4
    top = out_per[si[-q:]].sum()
    bot = out_per[si[:q]].sum()
    ratio = float(top / bot) if bot > 0 else 0
    return {
        "output_duration": round(actual, 1),
        "speed_min": round(float(curve.min()), 1),
        "speed_max": round(float(curve.max()), 1),
        "slow_pct": round(slow_pct, 0),
        "action_rest_ratio": round(ratio, 1),
    }


# ---- Endpoints ----

def _encode_thumbnails(thumbs) -> list[str]:
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
        if ch in _file_hashes:
            existing_id = _file_hashes[ch]
            if existing_id in _videos and _videos[existing_id].exists():
                tmp.unlink()
                dest = _videos[existing_id]
                info = get_video_info(str(dest))
                thumbs = generate_thumbnails(str(dest), n=8)
                return {
                    "video_id": existing_id,
                    "info": info,
                    "thumbnails": _encode_thumbnails(thumbs),
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
        thumbs = generate_thumbnails(str(dest), n=8)

        return {
            "video_id": video_id,
            "info": info,
            "thumbnails": _encode_thumbnails(thumbs),
            "cached": has_cache(str(dest)),
            "reused": False,
        }
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


@app.get("/api/videos")
async def list_videos():
    """List available input videos."""
    result = []
    for vid, path in _videos.items():
        info = get_video_info(str(path))
        result.append({"video_id": vid, "filename": path.name, "info": info})
    return result


@app.post("/api/analyze")
async def analyze_video(req: AnalyzeRequest):
    import queue, threading

    path = _get_video_path(req.video_id)
    video_path = str(path)

    progress_q: queue.Queue = queue.Queue()

    def run_analysis():
        """Run in a thread so progress events can be queued."""
        try:
            cached = load_analysis(video_path, expected_stride=req.stride) if not req.force else None

            if cached:
                poses, fps, _ = cached
                progress_q.put({"progress": 0.6, "message": "Loaded from cache"})
            else:
                progress_q.put({"progress": 0.02, "message": "Detecting poses..."})

                def pose_progress(p):
                    progress_q.put({
                        "progress": 0.02 + p * 0.53,
                        "message": f"Detecting poses... {int(p * 100)}%",
                    })

                poses, fps = extract_poses(video_path, stride=req.stride, progress_cb=pose_progress)
                progress_q.put({"progress": 0.55, "message": "Interpolating..."})

                n_missing = sum(1 for p in poses if p is None)
                if n_missing > 0:
                    poses = interpolate_missing_poses(poses)

                progress_q.put({"progress": 0.6, "message": "Scoring movement..."})
                default_scores = score_movement(poses, fps)
                save_analysis(video_path, poses, fps, default_scores, stride=req.stride)

            progress_q.put({"progress": 0.7, "message": "Computing progress scores..."})
            progress_scores = score_progress(poses, fps)
            action_scores = score_movement(poses, fps)

            progress_q.put({"progress": 0.85, "message": "Generating waveforms..."})

            n = len(progress_scores)
            step = max(1, n // 500)
            prog_ds = progress_scores[::step].tolist()
            act_ds = action_scores[::step].tolist()

            waveform_progress = render_waveform_data_url(progress_scores, fps)
            waveform_action = render_waveform_data_url(action_scores, fps)

            progress_q.put({
                "progress": 1.0,
                "message": "Done!",
                "done": True,
                "fps": fps,
                "frame_count": n,
                "duration": n / fps,
                "scores_progress": prog_ds,
                "scores_action": act_ds,
                "scores_step": step,
                "waveform_progress": waveform_progress,
                "waveform_action": waveform_action,
            })
        except Exception as e:
            progress_q.put({"progress": 0, "message": f"Error: {e}", "error": True})
        finally:
            progress_q.put(None)  # sentinel

    def generate():
        thread = threading.Thread(target=run_analysis, daemon=True)
        thread.start()

        while True:
            try:
                msg = progress_q.get(timeout=0.3)
            except queue.Empty:
                continue
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/solve")
async def solve_curve(req: SolveRequest):
    path = _get_video_path(req.video_id)
    cached = load_analysis(str(path))
    if not cached:
        raise HTTPException(400, "Run analyze first")

    poses, fps, _ = cached
    scores, curve, trimmed, start_frame = _compute_scores_and_curve(req, poses, fps)

    # Downsample curve for transfer — times are absolute (offset by trim start)
    n = len(curve)
    step = max(1, n // 500)
    curve_ds = curve[::step].tolist()
    trim_offset = start_frame / fps if fps > 0 else 0
    times_ds = ((np.arange(0, n, step) / fps) + trim_offset).tolist()

    stats = _curve_stats(curve, fps)

    return {
        "curve": curve_ds,
        "times": times_ds,
        "stats": stats,
    }


@app.post("/api/render")
async def render_video_endpoint(req: RenderRequest):
    import queue, threading

    path = _get_video_path(req.video_id)
    video_path = str(path)
    cached = load_analysis(video_path)
    if not cached:
        raise HTTPException(400, "Run analyze first")

    poses, fps, _ = cached
    progress_q: queue.Queue = queue.Queue()

    def run_render():
        try:
            progress_q.put({"progress": 0.05, "message": "Computing speed curve..."})

            scores, curve, trimmed, start_frame = _compute_scores_and_curve(
                SolveRequest(**{k: v for k, v in req.dict().items() if k in SolveRequest.__fields__}),
                poses, fps,
            )

            trim_start_s = start_frame / fps if fps > 0 else 0.0

            # Compute stabilization offsets from trimmed pose data
            stab_offsets = None
            stab_info = {}
            if req.stabilize:
                progress_q.put({"progress": 0.08, "message": "Computing stabilization..."})
                stab_dx, stab_dy = compute_stabilization_offsets(
                    trimmed, fps,
                    strength=req.stabilize_strength,
                    smooth_window_s=req.stabilize_smoothness,
                )
                stab_offsets = (stab_dx, stab_dy)
                stab_info = stabilization_stats(stab_dx, stab_dy)

            progress_q.put({"progress": 0.1, "message": "Rendering frames..."})

            if req.debug_overlay:
                overlay_fn = make_debug_overlay_fn(trimmed, scores, curve, fps)
            else:
                overlay_fn = make_speed_badge_fn(curve)

            output_id = uuid.uuid4().hex[:10]
            output_path = str(OUTPUT_DIR / f"{output_id}.mp4")

            def render_progress(p):
                progress_q.put({
                    "progress": 0.1 + p * 0.85,
                    "message": f"Rendering... {int(p * 100)}%",
                })

            render_preview(
                video_path, curve, fps,
                output_path=output_path,
                scale=req.scale,
                output_fps=req.output_fps,
                crf=req.crf,
                debug_overlay_fn=overlay_fn,
                progress_cb=render_progress,
                stabilize_offsets=stab_offsets,
                stabilize_crop=req.stabilize_crop,
                trim_start_s=trim_start_s,
            )

            stats = _curve_stats(curve, fps)
            stats.update(stab_info)
            progress_q.put({
                "progress": 1.0,
                "message": "Done!",
                "done": True,
                "output_id": output_id,
                "stats": stats,
            })
        except Exception as e:
            progress_q.put({"progress": 0, "message": f"Error: {e}", "error": True})
        finally:
            progress_q.put(None)

    def generate():
        thread = threading.Thread(target=run_render, daemon=True)
        thread.start()
        while True:
            try:
                msg = progress_q.get(timeout=0.3)
            except queue.Empty:
                continue
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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
    uvicorn.run(app, host="0.0.0.0", port=8000)
