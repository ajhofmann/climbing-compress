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
}

export interface CropBox {
  x: number; // left edge, normalized 0-1
  y: number; // top edge, normalized 0-1
  w: number; // width, normalized 0-1
  h: number; // height, normalized 0-1
}

export type AspectPreset = "9:16" | "1:1" | "4:5" | "16:9" | null;

export type SpeedMode = "progress" | "action";

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
}

export const DEFAULT_SETTINGS: Settings = {
  mode: "progress",
  targetDuration: 15,
  sensitivity: 0.35,
  maxSpeed: 10,
  minSpeed: 0.25,
  steepness: 14,
  smoothing: 0.3,
  handWeight: 2.0,
  footWeight: 1.0,
  coreWeight: 3.0,
  scale: 0.5,
  outputFps: 30,
  crf: 23,
  debugOverlay: true,
};
