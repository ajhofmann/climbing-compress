import { AnalysisData, Pin, Settings, SolveResult } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadVideo(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listVideos() {
  const res = await fetch(`${API}/api/videos`);
  return res.json();
}

export async function analyzeVideo(
  videoId: string,
  stride: number,
  force: boolean,
  onProgress: (progress: number, message: string) => void,
  useTracker: boolean = true,
  useFlow: boolean = true,
): Promise<AnalysisData | null> {
  const res = await fetch(`${API}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_id: videoId,
      stride,
      force,
      use_tracker: useTracker,
      use_flow: useFlow,
    }),
  });

  if (!res.ok) throw new Error(await res.text());
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let result: AnalysisData | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          onProgress(data.progress, data.message);
          if (data.done) result = data;
        } catch {
          // skip malformed SSE lines
        }
      }
    }
  }
  return result;
}

export async function solveCurve(
  videoId: string,
  settings: Settings,
  pins: Pin[],
): Promise<SolveResult> {
  const res = await fetch(`${API}/api/solve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_id: videoId,
      mode: settings.mode,
      target_duration: settings.targetDuration,
      sensitivity: settings.sensitivity,
      max_speed: settings.maxSpeed,
      min_speed: settings.minSpeed,
      steepness: settings.steepness,
      smoothing: settings.smoothing,
      hand_weight: settings.handWeight,
      foot_weight: settings.footWeight,
      core_weight: settings.coreWeight,
      progress_floor: settings.progressFloor,
      vertical_bias: settings.verticalBias,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      pins,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

interface RenderResult {
  output_id: string;
  stats: {
    output_duration: number;
    speed_min: number;
    speed_max: number;
    slow_pct: number;
    action_rest_ratio: number;
  };
}

export async function renderVideo(
  videoId: string,
  settings: Settings,
  pins: Pin[],
  onProgress: (progress: number, message: string) => void,
): Promise<RenderResult | null> {
  const res = await fetch(`${API}/api/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_id: videoId,
      mode: settings.mode,
      target_duration: settings.targetDuration,
      sensitivity: settings.sensitivity,
      max_speed: settings.maxSpeed,
      min_speed: settings.minSpeed,
      steepness: settings.steepness,
      smoothing: settings.smoothing,
      hand_weight: settings.handWeight,
      foot_weight: settings.footWeight,
      core_weight: settings.coreWeight,
      progress_floor: settings.progressFloor,
      vertical_bias: settings.verticalBias,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      pins,
      scale: settings.scale,
      output_fps: settings.outputFps,
      crf: settings.crf,
      debug_overlay: settings.debugOverlay,
      stabilize: settings.stabilize,
      stabilize_strength: settings.stabilizeStrength,
      stabilize_smoothness: settings.stabilizeSmoothness,
      stabilize_crop: settings.stabilizeCrop,
      include_audio: settings.includeAudio,
      use_feature_stabilize: settings.useFeatureStabilize,
      feature_stabilize_weight: settings.featureStabilizeWeight,
    }),
  });

  if (!res.ok) throw new Error(await res.text());
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let result: RenderResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          onProgress(data.progress, data.message);
          if (data.done) result = data;
        } catch {
          // skip malformed SSE lines
        }
      }
    }
  }
  return result;
}

export function videoUrl(id: string) {
  return `${API}/api/video/${id}`;
}
