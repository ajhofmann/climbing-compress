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
import time
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from pipeline.cache import (
    load_analysis, has_cache, content_hash, load_flow_scores,
    load_camera_motion, clear_cache, clear_cache_by_hash, has_cache_by_hash,
    CACHE_DIR,
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
VIDEO_NAME_INDEX = INPUT_DIR / "_video_names.json"
RENDER_HISTORY_INDEX = OUTPUT_DIR / "_render_history.json"
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "4096"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_COPY_CHUNK_BYTES = 8 * 1024 * 1024
ALLOWED_VIDEO_EXTS = (".mov", ".mp4", ".avi", ".mkv")
THUMB_PROFILE = "h480_q88"

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
# Reverse lookup for fast per-video cache checks (video_id -> hash)
_video_hashes: dict[str, str] = {}
# Video metadata cache (info + thumbnails) for fast local reloads
_video_meta_cache: dict[str, dict[str, object]] = {}
# Tracks source videos that failed decode for a given mtime
_video_info_errors: dict[str, float] = {}
# Tracks which unreadable videos have already been warned for current mtime
_unreadable_warned: dict[str, float] = {}


def _load_video_names() -> dict[str, str]:
    if not VIDEO_NAME_INDEX.exists():
        return {}
    try:
        raw = json.loads(VIDEO_NAME_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load %s: %s", VIDEO_NAME_INDEX, exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    names: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str):
            names[key] = value
    return names


def _persist_video_names() -> None:
    try:
        VIDEO_NAME_INDEX.parent.mkdir(parents=True, exist_ok=True)
        tmp = VIDEO_NAME_INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(_video_names, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(VIDEO_NAME_INDEX)
    except OSError as exc:
        logger.warning("Failed to persist %s: %s", VIDEO_NAME_INDEX, exc)


def _load_render_history() -> list[dict[str, object]]:
    if not RENDER_HISTORY_INDEX.exists():
        return []
    try:
        raw = json.loads(RENDER_HISTORY_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load %s: %s", RENDER_HISTORY_INDEX, exc)
        return []
    if not isinstance(raw, list):
        return []
    entries: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        output_id = item.get("output_id")
        video_id = item.get("video_id")
        if not isinstance(output_id, str) or not output_id:
            continue
        if not isinstance(video_id, str) or not video_id:
            continue
        entries.append(item)
    return entries


def _persist_render_history() -> None:
    try:
        RENDER_HISTORY_INDEX.parent.mkdir(parents=True, exist_ok=True)
        tmp = RENDER_HISTORY_INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(_render_history, indent=2), encoding="utf-8")
        tmp.replace(RENDER_HISTORY_INDEX)
    except OSError as exc:
        logger.warning("Failed to persist %s: %s", RENDER_HISTORY_INDEX, exc)


_video_names: dict[str, str] = _load_video_names()
_render_history: list[dict[str, object]] = _load_render_history()

# Scan existing input videos on startup
_video_names_dirty = False
for _f in INPUT_DIR.iterdir():
    if _f.suffix.lower() in ALLOWED_VIDEO_EXTS and not _f.name.startswith("_tmp_"):
        _videos[_f.stem] = _f
        if _f.stem not in _video_names:
            _video_names[_f.stem] = _f.name
            _video_names_dirty = True
        try:
            ch = content_hash(str(_f))
            _file_hashes[ch] = _f.stem
            _video_hashes[_f.stem] = ch
        except (OSError, ValueError) as exc:
            logger.warning("Failed to hash %s: %s", _f, exc)
if _video_names_dirty:
    _persist_video_names()


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
    scale: float = 1.0
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


class RenameVideoRequest(BaseModel):
    filename: str


# ---- Helpers ----

def _drop_video_state(
    video_id: str,
    *,
    remove_name: bool,
    persist_name_update: bool = True,
) -> bool:
    _videos.pop(video_id, None)
    _video_meta_cache.pop(video_id, None)
    _video_info_errors.pop(video_id, None)
    _unreadable_warned.pop(video_id, None)
    _video_hashes.pop(video_id, None)
    for h, vid in list(_file_hashes.items()):
        if vid == video_id:
            _file_hashes.pop(h, None)
    if remove_name and _video_names.pop(video_id, None) is not None:
        if persist_name_update:
            _persist_video_names()
        return True
    return False


def _get_video_path(video_id: str, *, require_exists: bool = True) -> Path:
    if video_id not in _videos:
        raise HTTPException(404, f"Video '{video_id}' not found")
    path = _videos[video_id]
    if require_exists and not path.exists():
        _drop_video_state(video_id, remove_name=True)
        raise HTTPException(404, f"Video '{video_id}' not found")
    return path


def _resolve_output_owner_video_id(path: Path) -> str | None:
    """Resolve source video ownership for an output file."""
    stem = path.stem

    # Metadata index is authoritative when available.
    for entry in _render_history:
        output_id = entry.get("output_id")
        if output_id != stem:
            continue
        owner = entry.get("video_id")
        if isinstance(owner, str) and owner:
            return owner

    # New format: "<content_hash>__<random_id>"
    if "__" in stem:
        maybe_hash, _, _ = stem.partition("__")
        if maybe_hash:
            owner = _file_hashes.get(maybe_hash)
            if owner:
                return owner

    # Legacy format: "<video_id>"
    if stem in _videos:
        return stem

    return None


def _output_file_stems() -> set[str]:
    stems: set[str] = set()
    if not OUTPUT_DIR.exists():
        return stems
    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTS:
            continue
        stems.add(path.stem)
    return stems


def _prune_render_history(*, persist: bool = True) -> bool:
    if not _render_history:
        return False

    existing_stems = _output_file_stems()
    kept: list[dict[str, object]] = []
    changed = False

    for entry in _render_history:
        output_id = entry.get("output_id")
        if not isinstance(output_id, str) or output_id not in existing_stems:
            changed = True
            continue

        comparison_id = entry.get("comparison_id")
        if isinstance(comparison_id, str) and comparison_id and comparison_id not in existing_stems:
            entry = dict(entry)
            entry["comparison_id"] = None
            changed = True

        kept.append(entry)

    if changed:
        _render_history.clear()
        _render_history.extend(kept)
        if persist:
            _persist_render_history()

    return changed


def _record_render_history_entry(
    req: RenderRequest,
    source_path: Path,
    video_hash: str | None,
    payload: dict[str, object],
) -> None:
    output_id = payload.get("output_id")
    if not isinstance(output_id, str) or not output_id:
        return

    comparison_id_raw = payload.get("comparison_id")
    comparison_id = comparison_id_raw if isinstance(comparison_id_raw, str) and comparison_id_raw else None

    output_path = OUTPUT_DIR / f"{output_id}.mp4"
    comparison_path = OUTPUT_DIR / f"{comparison_id}.mp4" if comparison_id else None
    stats = payload.get("stats")

    entry: dict[str, object] = {
        "output_id": output_id,
        "comparison_id": comparison_id,
        "video_id": req.video_id,
        "video_hash": video_hash,
        "video_filename": _display_filename(req.video_id, source_path),
        "created_at": int(time.time() * 1000),
        "stats": stats if isinstance(stats, dict) else {},
        "settings": {
            "mode": req.mode,
            "edit_mode": req.edit_mode,
            "target_duration": req.target_duration,
            "trim_start": req.trim_start,
            "trim_end": req.trim_end,
            "min_speed": req.min_speed,
            "max_speed": req.max_speed,
            "sensitivity": req.sensitivity,
            "smoothing": req.smoothing,
            "scale": req.scale,
            "output_fps": req.output_fps,
            "crf": req.crf,
            "output_aspect": req.output_aspect,
            "auto_reframe": req.auto_reframe,
            "debug_overlay": req.debug_overlay,
            "include_audio": req.include_audio,
            "stabilize": req.stabilize,
            "stabilize_strength": req.stabilize_strength,
            "stabilize_smoothness": req.stabilize_smoothness,
            "stabilize_crop": req.stabilize_crop,
            "use_feature_stabilize": req.use_feature_stabilize,
            "feature_stabilize_weight": req.feature_stabilize_weight,
            "render_comparison": req.render_comparison,
            "render_chapters": req.render_chapters,
        },
        "output_bytes": _safe_file_size(output_path),
        "comparison_bytes": _safe_file_size(comparison_path) if comparison_path is not None else 0,
    }

    _render_history.insert(0, entry)
    _prune_render_history(persist=False)
    _persist_render_history()


def _clear_output_videos() -> int:
    """Remove rendered output videos from local output directory."""
    deleted = 0
    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTS:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            raise HTTPException(500, f"Failed to delete output video: {exc}") from exc
    if deleted > 0:
        _prune_render_history()
    return deleted


def _clear_output_videos_for_source(video_id: str) -> int:
    """Remove rendered output files for one source video id."""
    deleted = 0
    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTS:
            continue
        if _resolve_output_owner_video_id(path) != video_id:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            raise HTTPException(500, f"Failed to delete output video: {exc}") from exc
    if deleted > 0:
        _prune_render_history()
    return deleted


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _copy_upload_to_path(file: UploadFile, path: Path) -> int:
    """Stream an upload to disk while enforcing the configured size limit."""
    total = 0
    with open(path, "wb") as f:
        while True:
            chunk = file.file.read(UPLOAD_COPY_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if MAX_UPLOAD_BYTES > 0 and total > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"Upload too large (limit {MAX_UPLOAD_MB} MB)")
            f.write(chunk)
    return total


def _output_video_totals() -> tuple[int, int]:
    """Return rendered output count + bytes across all source clips."""
    if not OUTPUT_DIR.exists():
        return 0, 0
    total = 0
    total_bytes = 0
    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTS:
            continue
        total += 1
        total_bytes += _safe_file_size(path)
    return total, total_bytes


def _output_video_totals_for_source(video_id: str) -> tuple[int, int]:
    """Return rendered output count + bytes for one source clip id."""
    if not OUTPUT_DIR.exists():
        return 0, 0
    total = 0
    total_bytes = 0
    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTS:
            continue
        if _resolve_output_owner_video_id(path) != video_id:
            continue
        total += 1
        total_bytes += _safe_file_size(path)
    return total, total_bytes


def _count_output_videos() -> int:
    total, _ = _output_video_totals()
    return total


def _count_output_videos_for_source(video_id: str) -> int:
    total, _ = _output_video_totals_for_source(video_id)
    return total


def _output_totals_by_source() -> dict[str, tuple[int, int]]:
    if not OUTPUT_DIR.exists():
        return {}
    totals: dict[str, tuple[int, int]] = {}
    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_VIDEO_EXTS:
            continue
        owner = _resolve_output_owner_video_id(path)
        if owner is None:
            continue
        count, byte_total = totals.get(owner, (0, 0))
        totals[owner] = (count + 1, byte_total + _safe_file_size(path))
    return totals


def _existing_clip_stats() -> tuple[int, int]:
    """Return existing local source clip count + bytes while pruning stale ids."""
    total = 0
    total_bytes = 0
    stale: list[str] = []
    for vid, path in list(_videos.items()):
        if path.exists():
            total += 1
            total_bytes += _safe_file_size(path)
        else:
            stale.append(vid)
    if stale:
        name_changed = False
        for vid in stale:
            if _drop_video_state(vid, remove_name=True, persist_name_update=False):
                name_changed = True
        if name_changed:
            _persist_video_names()
    return total, total_bytes


def _encode_thumbnails(thumbs: list[np.ndarray]) -> list[str]:
    """Encode thumbnail arrays as base64 data URLs."""
    from PIL import Image
    urls = []
    for t in thumbs:
        img = Image.fromarray(t)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        b64 = base64.b64encode(buf.getvalue()).decode()
        urls.append(f"data:image/jpeg;base64,{b64}")
    return urls


def _thumb_cache_dir(video_id: str) -> Path | None:
    """Return the disk cache directory for a video's thumbnails, or None if unhashed."""
    ch = _video_hashes.get(video_id)
    if not ch:
        return None
    return CACHE_DIR / ch


def _save_thumbs_to_disk(video_id: str, thumbs: list[str], profile: str) -> None:
    """Persist encoded thumbnail data URLs to disk for fast reload."""
    cache = _thumb_cache_dir(video_id)
    if not cache:
        return
    cache.mkdir(parents=True, exist_ok=True)
    manifest = {"profile": profile, "count": len(thumbs)}
    try:
        (cache / "thumbs.json").write_text(json.dumps(manifest))
        for i, data_url in enumerate(thumbs):
            # Strip data URL prefix and write raw JPEG bytes
            _, _, b64_data = data_url.partition(",")
            (cache / f"thumb_{i}.jpg").write_bytes(base64.b64decode(b64_data))
    except OSError as exc:
        logger.warning("Failed to save thumbnail cache for %s: %s", video_id, exc)


def _load_thumbs_from_disk(video_id: str) -> list[str] | None:
    """Load thumbnails from disk cache if they exist and match current profile."""
    cache = _thumb_cache_dir(video_id)
    if not cache:
        return None
    manifest_path = cache / "thumbs.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("profile") != THUMB_PROFILE:
            return None
        count = manifest.get("count", 0)
        thumbs: list[str] = []
        for i in range(count):
            jpg_path = cache / f"thumb_{i}.jpg"
            if not jpg_path.exists():
                return None
            b64 = base64.b64encode(jpg_path.read_bytes()).decode()
            thumbs.append(f"data:image/jpeg;base64,{b64}")
        return thumbs
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to load thumbnail cache for %s: %s", video_id, exc)
        return None


def _get_video_info_cached(video_id: str, path: Path) -> dict:
    entry = _video_meta_cache.get(video_id)
    if entry:
        info = entry.get("info")
        if isinstance(info, dict):
            return info
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _video_info_errors.get(video_id) == mtime:
        raise ValueError(f"Cannot open video: {path}")
    try:
        info = get_video_info(str(path))
    except (OSError, ValueError):
        _video_info_errors[video_id] = mtime
        raise
    _video_info_errors.pop(video_id, None)
    _video_meta_cache.setdefault(video_id, {})["info"] = info
    return info


def _get_thumbnails_cached(video_id: str, path: Path, n: int = 8) -> list[str]:
    # 1. In-memory cache
    entry = _video_meta_cache.get(video_id)
    if entry:
        thumbs = entry.get("thumbnails")
        profile = entry.get("thumb_profile")
        if isinstance(thumbs, list) and profile == THUMB_PROFILE:
            return thumbs
    # 2. Disk cache
    disk_thumbs = _load_thumbs_from_disk(video_id)
    if disk_thumbs is not None:
        meta = _video_meta_cache.setdefault(video_id, {})
        meta["thumbnails"] = disk_thumbs
        meta["thumb_profile"] = THUMB_PROFILE
        return disk_thumbs
    # 3. Generate fresh thumbnails via ffmpeg
    thumbs = _encode_thumbnails(generate_thumbnails(str(path), n=n))
    meta = _video_meta_cache.setdefault(video_id, {})
    meta["thumbnails"] = thumbs
    meta["thumb_profile"] = THUMB_PROFILE
    _save_thumbs_to_disk(video_id, thumbs, THUMB_PROFILE)
    return thumbs


def _display_filename(video_id: str, fallback: Path) -> str:
    return _video_names.get(video_id, fallback.name)


def _cache_key_for_video(video_id: str, path: Path) -> str | None:
    if video_id in _video_hashes:
        return _video_hashes[video_id]
    try:
        ch = content_hash(str(path))
    except (OSError, ValueError):
        return None
    _video_hashes[video_id] = ch
    _file_hashes[ch] = video_id
    return ch


def _has_cached_analysis(video_id: str, path: Path) -> bool:
    cache_key = _cache_key_for_video(video_id, path)
    if cache_key:
        return has_cache_by_hash(cache_key)
    # Fallback for unusual cases where hashing fails.
    return has_cache(str(path))


_prune_render_history()


# ---- Endpoints ----

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    filename = file.filename or ""
    display_name = Path(filename).name if filename else ""
    ext = Path(filename).suffix.lower() or ".mov"
    if ext not in ALLOWED_VIDEO_EXTS:
        allowed = ", ".join(ALLOWED_VIDEO_EXTS)
        raise HTTPException(415, f"Unsupported video format. Allowed: {allowed}")

    # Save to temp first so we can hash before committing
    tmp = INPUT_DIR / f"_tmp_{uuid.uuid4().hex[:8]}{ext}"
    try:
        _copy_upload_to_path(file, tmp)

        ch = content_hash(str(tmp))

        # Reuse existing file if same content already in input dir
        if ch in _file_hashes:
            existing_id = _file_hashes[ch]
            if existing_id in _videos and _videos[existing_id].exists():
                tmp.unlink()
                dest = _videos[existing_id]
                _video_hashes[existing_id] = ch
                if display_name and _video_names.get(existing_id) != display_name:
                    _video_names[existing_id] = display_name
                    _persist_video_names()
                info = _get_video_info_cached(existing_id, dest)
                thumbs = _get_thumbnails_cached(existing_id, dest, n=8)
                output_count, output_bytes = _output_video_totals_for_source(existing_id)
                return {
                    "video_id": existing_id,
                    "filename": _display_filename(existing_id, dest),
                    "info": info,
                    "thumbnails": thumbs,
                    "cached": _has_cached_analysis(existing_id, dest),
                    "output_count": output_count,
                    "source_bytes": _safe_file_size(dest),
                    "output_bytes": output_bytes,
                    "reused": True,
                }

        # New video — rename temp to final
        video_id = uuid.uuid4().hex[:10]
        dest = INPUT_DIR / f"{video_id}{ext}"
        tmp.rename(dest)

        _videos[video_id] = dest
        _file_hashes[ch] = video_id
        _video_hashes[video_id] = ch
        _video_names[video_id] = display_name or dest.name
        _video_info_errors.pop(video_id, None)
        _unreadable_warned.pop(video_id, None)
        _persist_video_names()
        info = get_video_info(str(dest))
        thumbs = _encode_thumbnails(generate_thumbnails(str(dest), n=8))
        _video_meta_cache[video_id] = {"info": info, "thumbnails": thumbs, "thumb_profile": THUMB_PROFILE}
        _save_thumbs_to_disk(video_id, thumbs, THUMB_PROFILE)
        output_count, output_bytes = _output_video_totals_for_source(video_id)

        return {
            "video_id": video_id,
            "filename": _display_filename(video_id, dest),
            "info": info,
            "thumbnails": thumbs,
            "cached": _has_cached_analysis(video_id, dest),
            "output_count": output_count,
            "source_bytes": _safe_file_size(dest),
            "output_bytes": output_bytes,
            "reused": False,
        }
    except HTTPException:
        if tmp.exists():
            tmp.unlink()
        raise
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

    output_totals = _output_totals_by_source()
    result = []
    stale_missing: list[str] = []
    for vid, path in sorted(_videos.items(), key=_sort_key):
        if not path.exists():
            stale_missing.append(vid)
            continue
        try:
            info = _get_video_info_cached(vid, path)
        except (OSError, ValueError) as exc:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            if _unreadable_warned.get(vid) != mtime:
                logger.warning("Skipping unreadable video %s: %s", path, exc)
                _unreadable_warned[vid] = mtime
            continue
        _unreadable_warned.pop(vid, None)
        output_count, output_bytes = output_totals.get(vid, (0, 0))
        thumb: str | None = None
        cache_entry = _video_meta_cache.get(vid)
        if cache_entry:
            cached_thumbs = cache_entry.get("thumbnails")
            if isinstance(cached_thumbs, list) and cached_thumbs:
                first = cached_thumbs[0]
                if isinstance(first, str):
                    thumb = first
        if thumb is None:
            # Try disk cache so listing shows thumbnails without lazy fetch
            disk_thumbs = _load_thumbs_from_disk(vid)
            if disk_thumbs:
                thumb = disk_thumbs[0]
                meta = _video_meta_cache.setdefault(vid, {})
                meta["thumbnails"] = disk_thumbs
                meta["thumb_profile"] = THUMB_PROFILE
        result.append({
            "video_id": vid,
            "filename": _display_filename(vid, path),
            "info": info,
            "thumbnail": thumb,
            "cached": _has_cached_analysis(vid, path),
            "output_count": output_count,
            "source_bytes": _safe_file_size(path),
            "output_bytes": output_bytes,
        })
    if stale_missing:
        name_changed = False
        for vid in stale_missing:
            if _drop_video_state(vid, remove_name=True, persist_name_update=False):
                name_changed = True
        if name_changed:
            _persist_video_names()
    return result


@app.get("/api/video-meta/{video_id}")
async def video_meta(video_id: str):
    """Fetch info + thumbnails for an already-uploaded source video."""
    path = _get_video_path(video_id)
    info = _get_video_info_cached(video_id, path)
    thumbs = _get_thumbnails_cached(video_id, path, n=8)
    output_count, output_bytes = _output_video_totals_for_source(video_id)
    return {
        "video_id": video_id,
        "filename": _display_filename(video_id, path),
        "info": info,
        "thumbnails": thumbs,
        "cached": _has_cached_analysis(video_id, path),
        "output_count": output_count,
        "source_bytes": _safe_file_size(path),
        "output_bytes": output_bytes,
    }


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    """Delete a source video from local library + clear its cached analysis."""
    path = _get_video_path(video_id, require_exists=False)
    deleted_bytes = _safe_file_size(path) if path.exists() else 0
    expected_outputs, expected_output_bytes = _output_video_totals_for_source(video_id)

    hash_keys = []
    if video_id in _video_hashes:
        hash_keys.append(_video_hashes[video_id])
    for h, vid in list(_file_hashes.items()):
        if vid == video_id and h not in hash_keys:
            hash_keys.append(h)

    if hash_keys:
        for cache_key in hash_keys:
            try:
                clear_cache_by_hash(cache_key)
            except OSError as exc:
                logger.warning("Failed to clear cache hash %s for %s: %s", cache_key, video_id, exc)
    elif path.exists():
        try:
            clear_cache(str(path))
        except OSError as exc:
            logger.warning("Failed to clear cache for deleted video %s: %s", video_id, exc)

    if path.exists():
        try:
            path.unlink()
        except OSError as exc:
            raise HTTPException(500, f"Failed to delete video: {exc}") from exc

    deleted_outputs = _clear_output_videos_for_source(video_id)
    _drop_video_state(video_id, remove_name=True)

    return {
        "video_id": video_id,
        "deleted": True,
        "deleted_outputs": deleted_outputs,
        "deleted_bytes": deleted_bytes,
        "deleted_output_bytes": expected_output_bytes if expected_outputs > 0 else 0,
    }


@app.delete("/api/outputs")
async def delete_all_outputs():
    """Delete all rendered output videos while keeping source clips."""
    expected_outputs, expected_output_bytes = _output_video_totals()
    deleted_outputs = _clear_output_videos()
    return {
        "deleted_outputs": deleted_outputs,
        "deleted_output_bytes": expected_output_bytes if expected_outputs > 0 else 0,
    }


@app.delete("/api/outputs/{video_id}")
async def delete_outputs_for_video(video_id: str):
    """Delete rendered outputs for one source video id."""
    expected_outputs, expected_output_bytes = _output_video_totals_for_source(video_id)
    deleted_outputs = _clear_output_videos_for_source(video_id)
    return {
        "video_id": video_id,
        "deleted_outputs": deleted_outputs,
        "deleted_output_bytes": expected_output_bytes if expected_outputs > 0 else 0,
    }


@app.get("/api/library-stats")
async def library_stats(video_id: str | None = None):
    """Small fast counters for local clip/output housekeeping UI."""
    clips, clip_bytes = _existing_clip_stats()
    outputs, output_bytes = _output_video_totals()
    stats: dict[str, int] = {
        "clips": clips,
        "outputs": outputs,
        "clip_bytes": clip_bytes,
        "output_bytes": output_bytes,
    }
    if video_id:
        clip_outputs, clip_output_bytes = _output_video_totals_for_source(video_id)
        stats["clip_outputs"] = clip_outputs
        stats["clip_output_bytes"] = clip_output_bytes
    return stats


@app.get("/api/renders")
async def list_renders(video_id: str | None = None, limit: int = 100):
    """List persisted render-history entries, newest first."""
    _prune_render_history()
    bounded_limit = max(1, min(limit, 500))
    rows = _render_history
    if video_id:
        rows = [entry for entry in rows if entry.get("video_id") == video_id]
    ordered = sorted(
        rows,
        key=lambda entry: int(entry.get("created_at", 0)) if isinstance(entry.get("created_at"), (int, float)) else 0,
        reverse=True,
    )
    return ordered[:bounded_limit]


@app.patch("/api/videos/{video_id}")
async def rename_video(video_id: str, req: RenameVideoRequest):
    path = _get_video_path(video_id)
    filename = Path(req.filename.strip()).name
    if not filename:
        raise HTTPException(400, "Filename cannot be empty")
    if Path(filename).suffix == "" and path.suffix:
        filename = f"{filename}{path.suffix.lower()}"
    ext = Path(filename).suffix.lower()
    if ext and ext not in ALLOWED_VIDEO_EXTS:
        allowed = ", ".join(ALLOWED_VIDEO_EXTS)
        raise HTTPException(400, f"Unsupported rename extension. Allowed: {allowed}")
    if len(filename) > 120:
        raise HTTPException(400, "Filename too long (max 120 characters)")

    if _video_names.get(video_id) == filename:
        return {
            "video_id": video_id,
            "filename": filename,
        }

    _video_names[video_id] = filename
    _persist_video_names()

    return {
        "video_id": video_id,
        "filename": filename,
    }


@app.delete("/api/videos")
async def delete_all_videos():
    """Delete all local source videos and clear related cached state."""
    removed_ids: list[str] = []
    deleted_bytes = 0

    for video_id, path in list(_videos.items()):
        hash_keys = []
        if video_id in _video_hashes:
            hash_keys.append(_video_hashes[video_id])
        for h, vid in list(_file_hashes.items()):
            if vid == video_id and h not in hash_keys:
                hash_keys.append(h)

        if hash_keys:
            for cache_key in hash_keys:
                try:
                    clear_cache_by_hash(cache_key)
                except OSError as exc:
                    logger.warning("Failed to clear cache hash %s for %s: %s", cache_key, video_id, exc)
        elif path.exists():
            try:
                clear_cache(str(path))
            except OSError as exc:
                logger.warning("Failed to clear cache for %s: %s", video_id, exc)

        if path.exists():
            deleted_bytes += _safe_file_size(path)
            try:
                path.unlink()
            except OSError as exc:
                raise HTTPException(500, f"Failed to delete video: {exc}") from exc

        _drop_video_state(video_id, remove_name=False)
        removed_ids.append(video_id)

    if _video_names:
        _video_names.clear()
        _persist_video_names()

    expected_outputs, expected_output_bytes = _output_video_totals()
    deleted_outputs = _clear_output_videos()
    removed_ids.sort()
    return {
        "deleted": len(removed_ids),
        "video_ids": removed_ids,
        "deleted_outputs": deleted_outputs,
        "deleted_bytes": deleted_bytes,
        "deleted_output_bytes": expected_output_bytes if expected_outputs > 0 else 0,
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
        output_prefix = _cache_key_for_video(req.video_id, path)
        def emit_with_history(payload: dict):
            emit(payload)
            if not payload.get("done"):
                return
            try:
                _record_render_history_entry(req, path, output_prefix, payload)
            except (OSError, ValueError) as exc:
                logger.warning("Failed to record render history for %s: %s", req.video_id, exc)

        run_render(str(path), req, OUTPUT_DIR, emit_with_history, output_prefix=output_prefix)

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
