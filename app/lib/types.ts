export interface VideoInfo {
  fps: number;
  width: number;
  height: number;
  frame_count: number;
  duration: number;
}

export interface Pin {
  time: number;
  speed: number;
  radius: number; // influence radius in seconds (default 2.0)
}

export interface Keyframe {
  time: number;
  speed: number;
}

export interface CurveStats {
  output_duration: number;
  speed_min: number;
  speed_max: number;
  slow_pct: number;
  action_rest_ratio: number;
}

export interface CruxPoint {
  time: number;
  score: number;
}

export interface SolveResult {
  curve: number[];
  times: number[];
  stats: CurveStats;
  scores: number[];
  rest_regions: [number, number][];
  crux_points: CruxPoint[];
}

export interface AnalysisData {
  fps: number;
  frame_count: number;
  duration: number;
  scores_progress: number[];
  scores_action: number[];
  scores_step: number;
  waveform_progress: string;
  waveform_action: string;
  tracker_available?: boolean;
  flow_available?: boolean;
  camera_motion_available?: boolean;
}

export type SpeedMode = "progress" | "action" | "hybrid";
export type EditMode = "pins" | "keyframes";
export type OutputAspect = "original" | "vertical" | "square";

export interface Settings {
  mode: SpeedMode;
  editMode: EditMode;
  targetDuration: number;
  sensitivity: number;
  progressActionBlend: number;
  maxSpeed: number;
  minSpeed: number;
  steepness: number;
  smoothing: number;
  handWeight: number;
  footWeight: number;
  coreWeight: number;
  scale: number;
  outputFps: number;
  crf: number;
  outputAspect: OutputAspect;
  autoReframe: boolean;
  debugOverlay: boolean;
  trimStart: number;
  trimEnd: number;
  // Analysis
  analyzeStride: number;
  useTracker: boolean;
  useFlow: boolean;
  trackerModel: string;
  // Constant progress mode
  progressFloor: number;
  verticalBias: number;
  downWeight: number;
  restThreshold: number;
  // Pose-anchored stabilization
  stabilize: boolean;
  stabilizeStrength: number;
  stabilizeSmoothness: number;
  stabilizeCrop: number;
  // Feature-based stabilization (blended with pose)
  useFeatureStabilize: boolean;
  featureStabilizeWeight: number;
  // Audio
  includeAudio: boolean;
  // Comparison
  renderComparison: boolean;
  // Chapter overlays
  renderChapters: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  mode: "progress",
  editMode: "pins",
  targetDuration: 15,
  sensitivity: 0.35,
  progressActionBlend: 0.5,
  maxSpeed: 15,
  minSpeed: 0.25,
  steepness: 14,
  smoothing: 1,
  handWeight: 2.0,
  footWeight: 1.0,
  coreWeight: 3.0,
  scale: 0.5,
  outputFps: 30,
  crf: 23,
  outputAspect: "original",
  autoReframe: false,
  debugOverlay: true,
  trimStart: 0,
  trimEnd: 0,
  analyzeStride: 1,
  useTracker: true,
  useFlow: true,
  trackerModel: "yolo26m",
  progressFloor: 0.02,
  verticalBias: 0.7,
  downWeight: 0.15,
  restThreshold: 0.3,
  stabilize: false,
  stabilizeStrength: 0.7,
  stabilizeSmoothness: 0.8,
  stabilizeCrop: 0.15,
  useFeatureStabilize: true,
  featureStabilizeWeight: 0.5,
  includeAudio: true,
  renderComparison: false,
  renderChapters: false,
};

export interface Preset {
  name: string;
  emoji: string;
  desc: string;
  /** Partial settings — merged onto DEFAULT_SETTINGS when applied */
  overrides: Partial<Settings>;
}

export const PRESETS: Preset[] = [
  {
    name: "Default",
    emoji: "🪨",
    desc: "balanced speed ramp",
    overrides: {},
  },
  {
    name: "Cinematic",
    emoji: "🎬",
    desc: "long, dramatic slow-mo",
    overrides: {
      mode: "progress",
      targetDuration: 25,
      minSpeed: 0.15,
      maxSpeed: 8,
      smoothing: 0.6,
      progressFloor: 0.01,
      verticalBias: 0.8,
      restThreshold: 0.5,
      outputFps: 24,
    },
  },
  {
    name: "Quick Reel",
    emoji: "📱",
    desc: "punchy 10s for social",
    overrides: {
      mode: "action",
      targetDuration: 10,
      sensitivity: 0.5,
      minSpeed: 0.4,
      maxSpeed: 15,
      steepness: 20,
      smoothing: 0.15,
    },
  },
  {
    name: "Max Drama",
    emoji: "🔥",
    desc: "extreme slow-mo on moves",
    overrides: {
      mode: "action",
      targetDuration: 20,
      sensitivity: 0.2,
      minSpeed: 0.1,
      maxSpeed: 12,
      steepness: 25,
      smoothing: 0.4,
      handWeight: 3.0,
      footWeight: 2.0,
      coreWeight: 5.0,
    },
  },
  {
    name: "Realtime",
    emoji: "▶️",
    desc: "subtle ramp, mostly 1x",
    overrides: {
      mode: "progress",
      targetDuration: 30,
      minSpeed: 0.8,
      maxSpeed: 3,
      smoothing: 0.5,
      progressFloor: 0.08,
      verticalBias: 0.6,
      restThreshold: 0.5,
    },
  },
];
