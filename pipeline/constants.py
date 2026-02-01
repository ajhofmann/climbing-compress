"""Shared constants used across the pipeline."""

# Minimum pose landmark visibility to consider a point valid.
# Used in movement scoring, stabilization, debug overlay, and smoothing.
MIN_VISIBILITY: float = 0.3

# Percentile used for score normalization.
# Normalizing to the 95th percentile (not max) prevents outlier spikes
# from squashing the rest of the signal.
NORM_PERCENTILE: int = 95

# Speed limits for the atempo FFmpeg filter chain.
ATEMPO_MIN: float = 0.5
ATEMPO_MAX: float = 100.0

# Absolute speed bounds for the raw speed curve (before atempo clamping).
SPEED_FLOOR: float = 0.01
SPEED_CEIL: float = 1000.0

# Duration solver tolerances (fraction of target duration).
SOLVER_TOLERANCE: float = 0.002          # bisection solver (progress mode)
SOLVER_TOLERANCE_ACTION: float = 0.005   # iterative solver (action mode)

# Bisection search bounds (multiplicative factor on speeds).
BISECT_LO: float = 0.01
BISECT_HI: float = 100.0
BISECT_MAX_ITER: int = 50
