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

# --- Progress scoring defaults ---

# Multiplier for downward COM movement.  Upward gets 1.0; downward gets
# this value.  Low values suppress readjustments and down-climbing from
# inflating the progress signal.
DEFAULT_DOWN_WEIGHT: float = 0.15

# Window (seconds) for directional consistency check.  Longer = more
# aggressive suppression of oscillatory rest sway.
DEFAULT_CONSISTENCY_WINDOW_S: float = 1.0

# Floor multiplier for directional consistency.  Prevents genuine slow
# climbing from being fully zeroed out.
DEFAULT_CONSISTENCY_FLOOR: float = 0.1

# --- Enhanced rest detection thresholds ---

# COM variance threshold (normalised coords, squared).  Below this the
# body position is considered stable.
DEFAULT_REST_COM_VARIANCE_THRESH: float = 0.0005

# Limb-to-body velocity ratio threshold.  Above this the limbs are
# considered active while the body centre is still (shakeout pattern).
DEFAULT_REST_LIMB_RATIO_THRESH: float = 5.0
