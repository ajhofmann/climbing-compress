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

export interface CurveStats {
  output_duration: number;
  speed_min: number;
  speed_max: number;
  slow_pct: number;
  action_rest_ratio: number;
}

export interface SolveResult {
  curve: number[];
  times: number[];
  stats: CurveStats;
  scores: number[];
  rest_regions: [number, number][];
}

export interface AnalysisData {
  fps: number;
  frame_count: number;
  duration: number;
  scores_progress: number[];
  scores_action: number[];
  scores_highlight?: number[];
  scores_step: number;
  waveform_progress: string;
  waveform_action: string;
  waveform_highlight?: string;
  tracker_available?: boolean;
  flow_available?: boolean;
  camera_motion_available?: boolean;
  people_max?: number;
  people_avg?: number;
}

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  created_at?: number;
}

export interface ProjectSummary {
  videos: number;
  outputs: number;
  jobs: number;
  latest_output?: {
    id: string;
    output_type: string;
    created_at: number;
  } | null;
}

export interface Metrics {
  videos: number;
  outputs: number;
  projects: number;
  jobs_by_type: Record<string, number>;
  jobs_by_status: Record<string, number>;
  avg_duration_by_type?: Record<string, number>;
}

export interface JobRecord {
  id: string;
  video_id: string;
  video_filename?: string | null;
  project_id?: string | null;
  project_name?: string | null;
  job_type: string;
  status: string;
  progress: number;
  message?: string | null;
  created_at?: number;
  updated_at?: number;
  result?: any;
}

export type SpeedMode = "progress" | "action" | "highlight";

export interface Settings {
  mode: SpeedMode;
  targetDuration: number;
  sensitivity: number;
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
  debugOverlay: boolean;
  trimStart: number;
  trimEnd: number;
  // Analysis
  analyzeStride: number;
  useTracker: boolean;
  useFlow: boolean;
  trackerModel: string;
  climberStrategy: string;
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
  // Queue mode
  queueMode: boolean;
  // Auto preview
  autoPreview: boolean;
  // Highlight blend
  highlightActionWeight: number;
  highlightProgressWeight: number;
}

export const DEFAULT_SETTINGS: Settings = {
  mode: "progress",
  targetDuration: 15,
  sensitivity: 0.35,
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
  debugOverlay: true,
  trimStart: 0,
  trimEnd: 0,
  analyzeStride: 1,
  useTracker: true,
  useFlow: true,
  trackerModel: "yolo26m",
  climberStrategy: "auto",
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
  queueMode: false,
  autoPreview: false,
  highlightActionWeight: 0.7,
  highlightProgressWeight: 0.3,
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
    name: "Highlights",
    emoji: "✨",
    desc: "action + progress blend",
    overrides: {
      mode: "highlight",
      targetDuration: 12,
      sensitivity: 0.4,
      minSpeed: 0.2,
      maxSpeed: 12,
      smoothing: 0.35,
    },
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
