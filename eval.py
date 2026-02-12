#!/usr/bin/env python3
"""Batch evaluation runner for climb-ramp on local videos.

Runs analysis (or reuses cache) and computes solve metrics for each config
across all clips in data/input. Writes:
  - detailed CSV: one row per (clip, config)
  - summary CSV: one row per config (aggregate means)

Examples:
  python eval.py
  python eval.py --limit 20 --target-duration 18
  python eval.py --configs-file data/eval/configs.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from pipeline.cache import load_analysis, load_camera_motion, load_flow_scores, load_tracks
from pipeline.orchestrate import compute_scores_and_curve, curve_stats, detect_crux_points, run_analysis
from pipeline.speed_curve import detect_rest

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}

# Request defaults aligned with app/lib/types.ts defaults.
BASE_SOLVE_REQ: dict[str, Any] = {
    "video_id": "",
    "mode": "progress",
    "edit_mode": "pins",
    "progress_action_blend": 0.5,
    "target_duration": 15.0,
    "sensitivity": 0.35,
    "max_speed": 15.0,
    "min_speed": 0.25,
    "steepness": 14.0,
    "smoothing": 1.0,
    "hand_weight": 2.0,
    "foot_weight": 1.0,
    "core_weight": 3.0,
    "progress_floor": 0.02,
    "vertical_bias": 0.7,
    "down_weight": 0.15,
    "rest_threshold_s": 0.3,
    "trim_start": 0.0,
    "trim_end": 0.0,
    "pins": [],
    "keyframes": [],
}

DEFAULT_CONFIGS: list[dict[str, Any]] = [
    {"name": "progress_baseline", "mode": "progress"},
    {"name": "progress_snappy", "mode": "progress", "smoothing": 0.6, "rest_threshold_s": 0.2},
    {"name": "progress_smooth", "mode": "progress", "smoothing": 1.4, "rest_threshold_s": 0.45, "max_speed": 12.0},
    {"name": "hybrid_35", "mode": "hybrid", "progress_action_blend": 0.35, "smoothing": 0.9},
    {"name": "hybrid_65", "mode": "hybrid", "progress_action_blend": 0.65, "smoothing": 0.9},
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate climb-ramp configs over local clips.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/input"), help="Directory containing source clips.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/eval"), help="Directory for evaluation CSV outputs.")
    parser.add_argument("--output-prefix", type=str, default="", help="Optional output filename prefix.")
    parser.add_argument("--configs-file", type=Path, default=None, help="Optional JSON file of configs to evaluate.")
    parser.add_argument("--limit", type=int, default=0, help="Evaluate only first N clips (0 = all).")
    parser.add_argument("--target-duration", type=float, default=15.0, help="Global target duration (seconds).")
    parser.add_argument("--stride", type=int, default=1, help="Pose extraction stride for analysis.")
    parser.add_argument("--use-tracker", action=argparse.BooleanOptionalAction, default=True, help="Use tracker during analysis.")
    parser.add_argument("--use-flow", action=argparse.BooleanOptionalAction, default=True, help="Use optical-flow/camera-motion analysis.")
    parser.add_argument("--force-analysis", action="store_true", help="Force re-analysis even when cache exists.")
    parser.add_argument("--tracker-model", type=str, default="yolo26m", help="Tracker model name (passed to run_analysis).")
    parser.add_argument("--crux-window-s", type=float, default=0.6, help="Half-window (seconds) around each crux for emphasis metrics.")
    parser.add_argument("--verbose", action="store_true", help="Print analysis progress events.")
    return parser.parse_args()


def _discover_clips(input_dir: Path, limit: int) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")
    clips = sorted(
        [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS],
        key=lambda p: p.name.lower(),
    )
    if limit > 0:
        clips = clips[:limit]
    return clips


def _analysis_req(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        stride=int(max(1, args.stride)),
        force=bool(args.force_analysis),
        use_tracker=bool(args.use_tracker),
        use_flow=bool(args.use_flow),
        tracker_model=str(args.tracker_model),
    )


def _ensure_analysis(video_path: Path, args: argparse.Namespace) -> tuple[list, float, np.ndarray]:
    cached = load_analysis(str(video_path), expected_stride=args.stride)
    needs_backfill = args.force_analysis or cached is None
    if not needs_backfill and cached is not None:
        if args.use_tracker and load_tracks(str(video_path), expected_stride=args.stride) is None:
            needs_backfill = True
        if args.use_flow and load_flow_scores(str(video_path)) is None:
            needs_backfill = True
        if args.use_flow and load_camera_motion(str(video_path)) is None:
            needs_backfill = True

    if cached is not None and not needs_backfill:
        return cached

    req = _analysis_req(args)

    def emit(event: dict[str, Any]) -> None:
        if not args.verbose:
            return
        msg = event.get("message")
        if msg:
            progress = event.get("progress", 0.0)
            print(f"      analyze {video_path.name}: {progress:.0%} {msg}")

    run_analysis(str(video_path), req, emit)
    cached = load_analysis(str(video_path), expected_stride=args.stride)
    if cached is None:
        raise RuntimeError(f"Analysis cache missing after run: {video_path}")
    return cached


def _validate_config_overrides(overrides: dict[str, Any]) -> None:
    allowed = set(BASE_SOLVE_REQ.keys()) - {"pins", "keyframes", "video_id"}
    unknown = sorted(set(overrides.keys()) - allowed - {"name"})
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(unknown)}")


def _load_configs(configs_file: Path | None) -> list[tuple[str, dict[str, Any]]]:
    if configs_file is None:
        return [(cfg["name"], {k: v for k, v in cfg.items() if k != "name"}) for cfg in DEFAULT_CONFIGS]

    data = json.loads(configs_file.read_text(encoding="utf-8"))
    configs: list[tuple[str, dict[str, Any]]] = []

    if isinstance(data, dict):
        for name, payload in data.items():
            if not isinstance(payload, dict):
                raise ValueError(f"Config '{name}' must map to an object")
            _validate_config_overrides(payload)
            configs.append((str(name), payload))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"Config entry index {idx} must be an object")
            name = str(item.get("name") or f"config_{idx+1:02d}")
            payload = {k: v for k, v in item.items() if k != "name"}
            _validate_config_overrides(payload)
            configs.append((name, payload))
    else:
        raise ValueError("configs-file JSON must be an object or array")

    if not configs:
        raise ValueError("No configs found to evaluate")
    return configs


def _build_req(video_id: str, target_duration: float, overrides: dict[str, Any]) -> SimpleNamespace:
    payload = dict(BASE_SOLVE_REQ)
    payload["video_id"] = video_id
    payload["target_duration"] = target_duration
    payload.update(overrides)
    payload["pins"] = []
    payload["keyframes"] = []
    return SimpleNamespace(**payload)


def _safe_pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return 100.0 * n / d


def _crux_emphasis(
    curve: np.ndarray,
    scores: np.ndarray,
    fps: float,
    window_s: float,
) -> tuple[int, float, float]:
    crux = detect_crux_points(scores, fps)
    if len(curve) == 0 or fps <= 0:
        return len(crux), float("nan"), float("nan")
    if not crux:
        return 0, float("nan"), float("nan")

    n = len(curve)
    window = max(1, int(window_s * fps))
    mask = np.zeros(n, dtype=bool)
    for fi, _ in crux:
        lo = max(0, fi - window)
        hi = min(n, fi + window + 1)
        mask[lo:hi] = True

    if not mask.any() or mask.all():
        return len(crux), float("nan"), float("nan")

    dt = 1.0 / fps
    out_time = dt / np.clip(curve, 1e-9, None)
    in_share = float(out_time[mask].sum() / out_time.sum())
    area_share = float(mask.mean())
    emphasis = in_share / max(area_share, 1e-9)  # >1 means more output-time density on crux windows

    med_in = float(np.median(curve[mask])) if mask.any() else float("nan")
    med_out = float(np.median(curve[~mask])) if (~mask).any() else float("nan")
    speed_ratio = med_out / med_in if med_in > 0 else float("nan")  # >1 means crux is slower than non-crux

    return len(crux), emphasis, speed_ratio


def _evaluate_one(
    video_path: Path,
    cfg_name: str,
    req: SimpleNamespace,
    poses: list,
    fps: float,
    flow_scores: np.ndarray | None,
    camera_motion: tuple[np.ndarray, np.ndarray] | None,
    crux_window_s: float,
) -> dict[str, Any]:
    scores, curve, _trimmed, _start_frame = compute_scores_and_curve(
        req,
        poses,
        fps,
        flow_scores=flow_scores,
        camera_motion=camera_motion,
    )
    if len(curve) == 0:
        raise ValueError("Empty curve")

    stats = curve_stats(curve, fps)
    target = float(req.target_duration)
    duration_err_s = abs(float(stats["output_duration"]) - target)
    duration_err_pct = _safe_pct(duration_err_s, target)

    eps = 1e-6
    at_min = curve <= float(req.min_speed) + eps
    at_max = curve >= float(req.max_speed) - eps
    clamp_min_pct = float(at_min.mean() * 100.0)
    clamp_max_pct = float(at_max.mean() * 100.0)
    clamp_any_pct = float((at_min | at_max).mean() * 100.0)

    log_curve = np.log(np.clip(curve, 1e-9, None))
    smooth_l1 = float(np.mean(np.abs(np.diff(log_curve)))) if len(curve) > 1 else 0.0
    smooth_l2 = float(np.mean(np.diff(log_curve) ** 2)) if len(curve) > 1 else 0.0

    rest_mask = detect_rest(scores, fps, float(req.rest_threshold_s))
    rest_pct = float(rest_mask.mean() * 100.0)
    rest_med = float(np.median(curve[rest_mask])) if rest_mask.any() else float("nan")
    active_mask = ~rest_mask
    active_med = float(np.median(curve[active_mask])) if active_mask.any() else float("nan")
    rest_speed_ratio = active_med / rest_med if rest_med > 0 else float("nan")  # >1 means rest is faster

    crux_count, crux_emphasis, crux_speed_ratio = _crux_emphasis(curve, scores, fps, crux_window_s)

    source_duration = len(poses) / fps if fps > 0 else 0.0

    return {
        "video": video_path.name,
        "video_id": video_path.stem,
        "config": cfg_name,
        "mode": str(req.mode),
        "target_duration": target,
        "source_duration": round(source_duration, 3),
        "output_duration": float(stats["output_duration"]),
        "duration_error_s": round(duration_err_s, 3),
        "duration_error_pct": round(duration_err_pct, 3),
        "speed_min": float(stats["speed_min"]),
        "speed_max": float(stats["speed_max"]),
        "slow_pct": float(stats["slow_pct"]),
        "action_rest_ratio": float(stats["action_rest_ratio"]),
        "clamp_min_pct": round(clamp_min_pct, 3),
        "clamp_max_pct": round(clamp_max_pct, 3),
        "clamp_any_pct": round(clamp_any_pct, 3),
        "smooth_l1": round(smooth_l1, 6),
        "smooth_l2": round(smooth_l2, 6),
        "rest_pct": round(rest_pct, 3),
        "rest_median_speed": round(rest_med, 6) if not math.isnan(rest_med) else float("nan"),
        "active_median_speed": round(active_med, 6) if not math.isnan(active_med) else float("nan"),
        "rest_speed_ratio": round(rest_speed_ratio, 6) if not math.isnan(rest_speed_ratio) else float("nan"),
        "crux_count": int(crux_count),
        "crux_emphasis": round(crux_emphasis, 6) if not math.isnan(crux_emphasis) else float("nan"),
        "crux_speed_ratio": round(crux_speed_ratio, 6) if not math.isnan(crux_speed_ratio) else float("nan"),
        "frames": int(len(curve)),
        "fps": round(float(fps), 3),
    }


def _group_mean(values: list[float]) -> float:
    arr = np.array([v for v in values if not (isinstance(v, float) and math.isnan(v))], dtype=float)
    if len(arr) == 0:
        return float("nan")
    return float(arr.mean())


def _summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_cfg: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cfg.setdefault(str(row["config"]), []).append(row)

    summary: list[dict[str, Any]] = []
    for cfg, cfg_rows in by_cfg.items():
        m_duration_err = _group_mean([float(r["duration_error_pct"]) for r in cfg_rows])
        m_clamp = _group_mean([float(r["clamp_any_pct"]) for r in cfg_rows])
        m_smooth = _group_mean([float(r["smooth_l1"]) for r in cfg_rows])
        m_crux_speed = _group_mean([float(r["crux_speed_ratio"]) for r in cfg_rows])
        m_rest_ratio = _group_mean([float(r["rest_speed_ratio"]) for r in cfg_rows])

        # Lower is better. Smoothness scaled so all terms are comparable.
        rank_score = (
            (m_duration_err if not math.isnan(m_duration_err) else 999.0)
            + 0.25 * (m_clamp if not math.isnan(m_clamp) else 999.0)
            + 20.0 * (m_smooth if not math.isnan(m_smooth) else 999.0)
        )

        summary.append(
            {
                "config": cfg,
                "rows": len(cfg_rows),
                "mode": cfg_rows[0]["mode"] if cfg_rows else "",
                "mean_duration_error_pct": round(m_duration_err, 4),
                "mean_clamp_any_pct": round(m_clamp, 4),
                "mean_smooth_l1": round(m_smooth, 6),
                "mean_crux_speed_ratio": round(m_crux_speed, 6) if not math.isnan(m_crux_speed) else float("nan"),
                "mean_rest_speed_ratio": round(m_rest_ratio, 6) if not math.isnan(m_rest_ratio) else float("nan"),
                "rank_score": round(rank_score, 6),
            }
        )

    summary.sort(key=lambda r: float(r["rank_score"]))
    return summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = _parse_args()
    clips = _discover_clips(args.input_dir, args.limit)
    if not clips:
        print(f"No clips found in {args.input_dir}")
        return 1

    configs = _load_configs(args.configs_file)
    print(f"Evaluating {len(configs)} configs across {len(clips)} clips...")

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for idx, clip in enumerate(clips, start=1):
        print(f"[{idx}/{len(clips)}] {clip.name}")

        try:
            poses, fps, _ = _ensure_analysis(clip, args)
        except Exception as exc:  # pragma: no cover - runtime reporting
            failures.append({"video": clip.name, "config": "*analysis*", "error": str(exc)})
            print(f"    analysis failed: {exc}")
            continue

        flow_scores = load_flow_scores(str(clip))
        camera_motion = load_camera_motion(str(clip))

        for cfg_name, overrides in configs:
            req = _build_req(clip.stem, args.target_duration, overrides)
            try:
                row = _evaluate_one(
                    clip,
                    cfg_name,
                    req,
                    poses,
                    fps,
                    flow_scores,
                    camera_motion,
                    args.crux_window_s,
                )
                rows.append(row)
            except Exception as exc:  # pragma: no cover - runtime reporting
                failures.append({"video": clip.name, "config": cfg_name, "error": str(exc)})
                print(f"    {cfg_name}: failed ({exc})")

    if not rows:
        print("No evaluation rows produced.")
        return 2

    summary = _summarize(rows)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = f"{args.output_prefix.strip()}-" if args.output_prefix.strip() else ""
    detailed_path = args.output_dir / f"{prefix}eval-{ts}.csv"
    summary_path = args.output_dir / f"{prefix}eval-{ts}-summary.csv"
    failures_path = args.output_dir / f"{prefix}eval-{ts}-failures.csv"

    _write_csv(detailed_path, rows)
    _write_csv(summary_path, summary)
    if failures:
        _write_csv(failures_path, failures)

    print("")
    print(f"Wrote detailed metrics: {detailed_path}")
    print(f"Wrote summary metrics:  {summary_path}")
    if failures:
        print(f"Wrote failures log:    {failures_path}")
    print("")
    print("Top configs by rank_score (lower is better):")
    for s in summary[: min(5, len(summary))]:
        print(
            f"  - {s['config']}: score={s['rank_score']:.4f}, "
            f"dur_err={s['mean_duration_error_pct']:.3f}%, "
            f"clamp={s['mean_clamp_any_pct']:.2f}%, "
            f"smooth={s['mean_smooth_l1']:.4f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
