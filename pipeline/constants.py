"""Shared constants used across the pipeline."""

# Minimum pose landmark visibility to consider a point valid.
# Used in movement scoring, stabilization, debug overlay, and smoothing.
MIN_VISIBILITY: float = 0.3

# --- Tracking robustness ---

# YOLO model variant for person detection.
# Options: "yolo26n.pt", "yolo26s.pt", "yolo26m.pt", "yolo26l.pt"
# Larger models are slower but far more reliable on unusual climbing poses.
# YOLO26 is NMS-free and 43% faster on CPU than YOLO11 at equal accuracy.
YOLO_MODEL: str = "yolo26m.pt"

# Consecutive missing frames before declaring tracking lost.
TRACK_LOST_GAP_FRAMES: int = 15

# Max normalized center jump per frame before rejecting a track.
TRACK_MAX_JUMP_NORM: float = 0.25

# Expanded crop margin when recovering from tracking loss.
TRACK_RECOVERY_MARGIN: float = 0.35

# Max gap size to interpolate or edge-fill in tracks.
TRACK_EDGE_FILL_MAX_FRAMES: int = 15

# ByteTrack lost_track_buffer — how many frames a lost identity survives.
# Default (30) is short for climbing; 90 lets it survive brief occlusions.
BYTETRACK_LOST_TRACK_BUFFER: int = 90

# Consecutive misses before entering SEARCHING state (relaxed gate).
TRACK_SEARCH_GAP_FRAMES: int = 4

# Max-jump multiplier applied in SEARCHING state so the tracker can
# reach further for the climber without a full reset.
TRACK_SEARCH_MAX_JUMP_SCALE: float = 3.0

# Minimum confidence to accept a high-confidence re-lock in SEARCHING
# state regardless of distance from last known position.
TRACK_RELOCK_CONF: float = 0.6

# Rolling window (detections) for track quality monitoring.
TRACK_QUALITY_WINDOW: int = 10

# If rolling mean confidence drops below this while LOCKED, transition
# to SEARCHING proactively (likely tracking the wrong person).
TRACK_QUALITY_MIN_CONF: float = 0.35

# Confidence for fallback re-detection when primary detection misses.
TRACK_FALLBACK_CONF: float = 0.15

# Resolution multiplier for fallback re-detection (relative to base).
TRACK_FALLBACK_RESOLUTION: int = 960

# Adaptive pose extraction fallback:
# If tracker-guided pose sanitization drops too many frames, retry full-frame
# extraction and switch when it materially improves quality.
POSE_ADAPTIVE_SANITIZE_DROP_PCT: float = 60.0
POSE_ADAPTIVE_SANITIZE_DROP_MIN_FRAMES: int = 120
POSE_ADAPTIVE_MIN_IMPROVEMENT_PCT: float = 8.0

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
