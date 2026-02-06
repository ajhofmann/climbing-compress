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
import threading
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline.cache import (
    load_analysis, has_cache, content_hash, load_flow_scores,
    load_camera_motion, CACHE_DIR,
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
    set_video_project,
    insert_project,
    update_project,
    get_project,
    get_project_summary,
    delete_project,
    list_projects as db_list_projects,
    insert_job,
    update_job,
    get_job as db_get_job,
    list_jobs as db_list_jobs,
    insert_output,
    get_output as db_get_output,
    list_outputs as db_list_outputs,
    get_metrics as db_get_metrics,
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
    highlight_action_weight: float = 0.7
    highlight_progress_weight: float = 0.3

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
    climber_strategy: str = "auto"
    highlight_action_weight: float = 0.7
    highlight_progress_weight: float = 0.3

class PreviewRequest(RenderRequest):
    preview_start: float = 0.0
    preview_duration: float = 4.0
    preview_scale: float = 0.35
    preview_fps: float = 24
    preview_crf: int = 28
    preview_debug_overlay: bool = False

class ProjectRequest(BaseModel):
    name: str
    description: str | None = None

class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None

class ProjectAssignRequest(BaseModel):
    project_id: str | None = None


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


def _model_dump(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class JobCancelled(Exception):
    pass


def _ensure_job_active(job_id: str) -> None:
    job = db_get_job(job_id)
    if job and job.get("status") == "cancelled":
        raise JobCancelled()


def _build_preview_request(req: PreviewRequest, path: Path) -> RenderRequest:
    info = get_video_info(str(path))
    duration = float(info.get("duration", 0))
    start = max(0.0, req.preview_start)
    preview_len = max(0.5, req.preview_duration)
    end = start + preview_len
    if duration > 0:
        end = min(end, duration)

    payload = _model_dump(req)
    for key in [
        "preview_start", "preview_duration", "preview_scale",
        "preview_fps", "preview_crf", "preview_debug_overlay",
    ]:
        payload.pop(key, None)
    payload.update({
        "trim_start": start,
        "trim_end": end,
        "scale": req.preview_scale,
        "output_fps": req.preview_fps,
        "crf": req.preview_crf,
        "debug_overlay": req.preview_debug_overlay,
        "render_comparison": False,
    })
    return RenderRequest(**payload)


def _analysis_job_worker(job_id: str, path: Path, req: AnalyzeRequest, emit) -> None:
    update_job(job_id, status="running", progress=0.0, message="Starting analysis")

    def emit_job(payload: dict) -> None:
        _ensure_job_active(job_id)
        payload = {**payload, "job_id": job_id}
        update_job(
            job_id,
            status="running",
            progress=float(payload.get("progress", 0.0)),
            message=payload.get("message"),
        )
        if payload.get("done"):
            update_job(
                job_id,
                status="success",
                progress=1.0,
                message=payload.get("message", "Done"),
                result=payload,
            )
        emit(payload)

    try:
        run_analysis(str(path), req, emit_job)
    except JobCancelled:
        update_job(job_id, status="cancelled", message="Cancelled")
    except Exception as exc:
        update_job(job_id, status="failed", message=str(exc))
        raise


def _render_job_worker(job_id: str, path: Path, req: RenderRequest, emit) -> None:
    update_job(job_id, status="running", progress=0.0, message="Starting render")

    def emit_job(payload: dict) -> None:
        _ensure_job_active(job_id)
        payload = {**payload, "job_id": job_id}
        update_job(
            job_id,
            status="running",
            progress=float(payload.get("progress", 0.0)),
            message=payload.get("message"),
        )
        if payload.get("done"):
            output_id = payload.get("output_id")
            if output_id:
                output_path = OUTPUT_DIR / f"{output_id}.mp4"
                insert_output(
                    output_id=output_id,
                    video_id=req.video_id,
                    job_id=job_id,
                    output_type="main",
                    path=str(output_path),
                    stats=payload.get("stats"),
                )
            comparison_id = payload.get("comparison_id")
            if comparison_id:
                comparison_path = OUTPUT_DIR / f"{comparison_id}.mp4"
                insert_output(
                    output_id=comparison_id,
                    video_id=req.video_id,
                    job_id=job_id,
                    output_type="comparison",
                    path=str(comparison_path),
                    stats=payload.get("stats"),
                )
            update_job(
                job_id,
                status="success",
                progress=1.0,
                message=payload.get("message", "Done"),
                result=payload,
            )
        emit(payload)

    try:
        run_render(str(path), req, OUTPUT_DIR, emit_job)
    except JobCancelled:
        update_job(job_id, status="cancelled", message="Cancelled")
    except Exception as exc:
        update_job(job_id, status="failed", message=str(exc))
        raise


def _preview_job_worker(job_id: str, path: Path, req: RenderRequest, emit) -> None:
    update_job(job_id, status="running", progress=0.0, message="Starting preview render")

    def emit_job(payload: dict) -> None:
        _ensure_job_active(job_id)
        payload = {**payload, "job_id": job_id}
        update_job(
            job_id,
            status="running",
            progress=float(payload.get("progress", 0.0)),
            message=payload.get("message"),
        )
        if payload.get("done"):
            output_id = payload.get("output_id")
            if output_id:
                output_path = OUTPUT_DIR / f"{output_id}.mp4"
                insert_output(
                    output_id=output_id,
                    video_id=req.video_id,
                    job_id=job_id,
                    output_type="preview",
                    path=str(output_path),
                    stats=payload.get("stats"),
                )
            update_job(
                job_id,
                status="success",
                progress=1.0,
                message=payload.get("message", "Done"),
                result=payload,
            )
        emit(payload)

    try:
        run_render(str(path), req, OUTPUT_DIR, emit_job)
    except JobCancelled:
        update_job(job_id, status="cancelled", message="Cancelled")
    except Exception as exc:
        update_job(job_id, status="failed", message=str(exc))
        raise


def _start_background(worker, *args) -> None:
    thread = threading.Thread(target=worker, args=(*args, lambda _payload: None), daemon=True)
    thread.start()


# ---- Endpoints ----

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...), project_id: str | None = Query(default=None)):
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
                if project_id is not None:
                    set_video_project(existing_id, project_id)
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
        register_video(video_id, dest.name, str(dest), ch, info=info, project_id=project_id)

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
async def list_videos(project_id: str | None = Query(default=None)):
    """List available input videos."""
    result = []
    for record in db_list_videos(project_id=project_id):
        path = Path(record["path"])
        if not path.exists():
            continue
        size_bytes = path.stat().st_size
        if record.get("info_json"):
            info = json.loads(record["info_json"])
        else:
            info = get_video_info(str(path))
            update_video_info(record["id"], info)
        result.append({
            "video_id": record["id"],
            "filename": record["filename"],
            "info": info,
            "project_id": record.get("project_id"),
            "project_name": record.get("project_name"),
            "created_at": record.get("created_at"),
            "size_bytes": size_bytes,
            "cached": has_cache(str(path)),
        })
    return result


@app.post("/api/analyze")
async def analyze_video(req: AnalyzeRequest):
    path = _get_video_path(req.video_id)
    job_id = uuid.uuid4().hex[:12]
    insert_job(job_id, req.video_id, "analyze", status="queued", message="Queued", request=_model_dump(req))

    return sse_response(lambda emit: _analysis_job_worker(job_id, path, req, emit))


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
    job_id = uuid.uuid4().hex[:12]
    insert_job(job_id, req.video_id, "render", status="queued", message="Queued", request=_model_dump(req))

    return sse_response(lambda emit: _render_job_worker(job_id, path, req, emit))


@app.post("/api/preview")
async def preview_video(req: PreviewRequest):
    path = _get_video_path(req.video_id)
    job_id = uuid.uuid4().hex[:12]
    insert_job(job_id, req.video_id, "preview", status="queued", message="Queued", request=_model_dump(req))
    preview_req = _build_preview_request(req, path)
    return sse_response(lambda emit: _preview_job_worker(job_id, path, preview_req, emit))


@app.post("/api/jobs/analyze")
async def enqueue_analyze(req: AnalyzeRequest, run_background: bool = Query(default=True)):
    path = _get_video_path(req.video_id)
    job_id = uuid.uuid4().hex[:12]
    insert_job(job_id, req.video_id, "analyze", status="queued", message="Queued", request=_model_dump(req))
    if run_background:
        _start_background(_analysis_job_worker, job_id, path, req)
    return {"job_id": job_id}


@app.post("/api/jobs/render")
async def enqueue_render(req: RenderRequest, run_background: bool = Query(default=True)):
    path = _get_video_path(req.video_id)
    job_id = uuid.uuid4().hex[:12]
    insert_job(job_id, req.video_id, "render", status="queued", message="Queued", request=_model_dump(req))
    if run_background:
        _start_background(_render_job_worker, job_id, path, req)
    return {"job_id": job_id}


@app.post("/api/jobs/preview")
async def enqueue_preview(req: PreviewRequest, run_background: bool = Query(default=True)):
    path = _get_video_path(req.video_id)
    job_id = uuid.uuid4().hex[:12]
    insert_job(job_id, req.video_id, "preview", status="queued", message="Queued", request=_model_dump(req))
    preview_req = _build_preview_request(req, path)
    if run_background:
        _start_background(_preview_job_worker, job_id, path, preview_req)
    return {"job_id": job_id}


@app.get("/api/video/{video_id}")
async def serve_video(video_id: str):
    # Check output first, then input
    for d in [OUTPUT_DIR, INPUT_DIR]:
        for f in d.iterdir():
            if f.stem == video_id:
                return FileResponse(str(f), media_type="video/mp4")
    raise HTTPException(404, "Video not found")


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = db_get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    result = None
    if job.get("result_json"):
        try:
            result = json.loads(job["result_json"])
        except json.JSONDecodeError:
            result = None
    request = None
    if job.get("request_json"):
        try:
            request = json.loads(job["request_json"])
        except json.JSONDecodeError:
            request = None
    return {
        "id": job["id"],
        "video_id": job["video_id"],
        "job_type": job["job_type"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "result": result,
        "request": request,
    }


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = db_get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in ("success", "failed", "cancelled"):
        return {"id": job_id, "status": job["status"]}
    update_job(job_id, status="cancelled", message="Cancelled")
    return {"id": job_id, "status": "cancelled"}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    job = db_get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] not in ("failed", "cancelled"):
        return {"job_id": job_id, "status": job["status"]}
    request_payload = None
    if job.get("request_json"):
        try:
            request_payload = json.loads(job["request_json"])
        except json.JSONDecodeError:
            request_payload = None
    if not request_payload:
        raise HTTPException(400, "Job request payload missing")

    new_job_id = uuid.uuid4().hex[:12]
    insert_job(
        new_job_id,
        job["video_id"],
        job["job_type"],
        status="queued",
        message="Queued",
        request=request_payload,
    )
    return {"job_id": new_job_id, "status": "queued"}


@app.get("/api/jobs")
async def list_jobs(
    video_id: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
):
    jobs = db_list_jobs(
        video_id=video_id,
        job_type=job_type,
        status=status,
        project_id=project_id,
    )
    payload = []
    for job in jobs:
        payload.append({
            "id": job["id"],
            "video_id": job["video_id"],
            "video_filename": job.get("video_filename"),
            "project_id": job.get("project_id"),
            "project_name": job.get("project_name"),
            "job_type": job["job_type"],
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        })
    return payload


@app.get("/api/outputs/{output_id}")
async def get_output(output_id: str):
    output = db_get_output(output_id)
    if not output:
        raise HTTPException(404, "Output not found")
    stats = None
    if output.get("stats_json"):
        try:
            stats = json.loads(output["stats_json"])
        except json.JSONDecodeError:
            stats = None
    return {
        "id": output["id"],
        "video_id": output["video_id"],
        "job_id": output["job_id"],
        "output_type": output["output_type"],
        "path": output["path"],
        "stats": stats,
        "created_at": output["created_at"],
    }


@app.get("/api/outputs")
async def list_outputs(
    video_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
):
    outputs = db_list_outputs(video_id=video_id, project_id=project_id)
    payload = []
    for output in outputs:
        size_bytes = None
        output_path = Path(output.get("path", ""))
        if output_path.is_file():
            size_bytes = output_path.stat().st_size
        else:
            fallback = OUTPUT_DIR / f"{output.get('id')}.mp4"
            if fallback.is_file():
                size_bytes = fallback.stat().st_size
        stats = None
        if output.get("stats_json"):
            try:
                stats = json.loads(output["stats_json"])
            except json.JSONDecodeError:
                stats = None
        payload.append({
            "id": output["id"],
            "video_id": output["video_id"],
            "video_filename": output.get("video_filename"),
            "project_id": output.get("project_id"),
            "project_name": output.get("project_name"),
            "job_id": output["job_id"],
            "output_type": output["output_type"],
            "path": output["path"],
            "created_at": output["created_at"],
            "output_duration": stats.get("output_duration") if stats else None,
            "size_bytes": size_bytes,
        })
    return payload


@app.get("/api/projects")
async def list_projects():
    projects = db_list_projects()
    return [
        {
            "id": project["id"],
            "name": project["name"],
            "description": project["description"],
            "created_at": project["created_at"],
        }
        for project in projects
    ]


@app.post("/api/projects")
async def create_project(req: ProjectRequest):
    project_id = uuid.uuid4().hex[:10]
    insert_project(project_id, req.name, req.description)
    return {
        "id": project_id,
        "name": req.name,
        "description": req.description,
    }


@app.patch("/api/projects/{project_id}")
async def update_project_endpoint(project_id: str, req: ProjectUpdateRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    update_project(project_id, name=req.name, description=req.description)
    refreshed = get_project(project_id)
    return {
        "id": refreshed["id"],
        "name": refreshed["name"],
        "description": refreshed["description"],
        "created_at": refreshed["created_at"],
    }


@app.get("/api/projects/{project_id}/summary")
async def project_summary(project_id: str):
    if project_id != "unassigned":
        project = get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
    return get_project_summary(project_id)


@app.delete("/api/projects/{project_id}")
async def delete_project_endpoint(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    delete_project(project_id)
    return {"id": project_id, "deleted": True}


@app.post("/api/videos/{video_id}/project")
async def assign_video_project(video_id: str, req: ProjectAssignRequest):
    record = get_video(video_id)
    if not record:
        raise HTTPException(404, "Video not found")
    if req.project_id:
        project = get_project(req.project_id)
        if not project:
            raise HTTPException(404, "Project not found")
    set_video_project(video_id, req.project_id)
    return {"video_id": video_id, "project_id": req.project_id}


@app.get("/api/metrics")
async def metrics():
    metrics_payload = db_get_metrics()
    output_storage_bytes = 0
    input_storage_bytes = 0
    cache_storage_bytes = 0
    try:
        for file in OUTPUT_DIR.glob("*.mp4"):
            if file.is_file():
                output_storage_bytes += file.stat().st_size
    except FileNotFoundError:
        output_storage_bytes = 0
    try:
        for file in INPUT_DIR.iterdir():
            if file.is_file():
                input_storage_bytes += file.stat().st_size
    except FileNotFoundError:
        input_storage_bytes = 0
    try:
        if CACHE_DIR.exists():
            for file in CACHE_DIR.rglob("*"):
                if file.is_file():
                    cache_storage_bytes += file.stat().st_size
    except FileNotFoundError:
        cache_storage_bytes = 0
    metrics_payload["output_storage_bytes"] = output_storage_bytes
    metrics_payload["input_storage_bytes"] = input_storage_bytes
    metrics_payload["cache_storage_bytes"] = cache_storage_bytes
    return metrics_payload


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
