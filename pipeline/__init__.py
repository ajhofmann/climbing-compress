"""climb-ramp video processing pipeline.

Public API re-exports for convenient access::

    from pipeline import extract_poses, score_movement, solve_speed_curve
    from pipeline import run_analysis, run_render
"""

from pipeline.pose import extract_poses, interpolate_missing_poses
from pipeline.movement import score_movement, score_progress
from pipeline.speed_curve import solve_speed_curve, solve_constant_progress
from pipeline.render import render_preview
from pipeline.stabilize import compute_stabilization_offsets
from pipeline.orchestrate import run_analysis, run_render

__all__ = [
    "extract_poses",
    "interpolate_missing_poses",
    "score_movement",
    "score_progress",
    "solve_speed_curve",
    "solve_constant_progress",
    "render_preview",
    "compute_stabilization_offsets",
    "run_analysis",
    "run_render",
]
