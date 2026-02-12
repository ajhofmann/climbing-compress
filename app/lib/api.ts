import { AnalysisData, Keyframe, Pin, Settings, SolveResult, VideoInfo } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type SseProgress = {
  progress?: number;
  message?: string;
  done?: boolean;
};

interface UploadResult {
  video_id: string;
  filename: string;
  info: VideoInfo;
  thumbnails: string[];
  cached: boolean;
  output_count: number;
  source_bytes: number;
  output_bytes: number;
  reused: boolean;
}

async function readErrorMessage(res: Response): Promise<string> {
  const text = await res.text();
  if (!text) return `${res.status} ${res.statusText}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (typeof parsed.message === "string") return parsed.message;
  } catch {
    // Fall through to raw text.
  }
  return text;
}

async function consumeSseJson<T>(
  res: Response,
  onProgress: (progress: number, message: string) => void,
): Promise<T | null> {
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: T | null = null;

  const handleEvent = (block: string) => {
    const lines = block.split(/\r?\n/);
    const dataLines: string[] = [];
    for (const raw of lines) {
      const line = raw.trim();
      if (!line.startsWith("data:")) continue;
      dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return;

    try {
      const payload = JSON.parse(dataLines.join("\n")) as SseProgress & T;
      onProgress(payload.progress ?? 0, payload.message ?? "");
      if (payload.done) result = payload;
    } catch {
      // Ignore malformed events and keep consuming stream.
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split(/\r?\n\r?\n/);
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      if (chunk.trim()) handleEvent(chunk);
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) handleEvent(buffer);

  return result;
}

export async function uploadVideo(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function analyzeVideo(
  videoId: string,
  stride: number,
  force: boolean,
  onProgress: (progress: number, message: string) => void,
  useTracker: boolean = true,
  useFlow: boolean = true,
  trackerModel: string = "yolo26m",
  signal?: AbortSignal,
): Promise<AnalysisData | null> {
  const res = await fetch(`${API}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      video_id: videoId,
      stride,
      force,
      use_tracker: useTracker,
      use_flow: useFlow,
      tracker_model: trackerModel,
    }),
  });

  if (!res.ok) throw new Error(await readErrorMessage(res));
  return consumeSseJson<AnalysisData>(res, onProgress);
}

export async function solveCurve(
  videoId: string,
  settings: Settings,
  pins: Pin[],
  keyframes: Keyframe[],
  signal?: AbortSignal,
): Promise<SolveResult> {
  const res = await fetch(`${API}/api/solve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      video_id: videoId,
      mode: settings.mode,
      edit_mode: settings.editMode,
      progress_action_blend: settings.progressActionBlend,
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      pins,
      keyframes,
    }),
  });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export interface RenderStatsSummary {
  output_duration: number;
  speed_min: number;
  speed_max: number;
  slow_pct: number;
  action_rest_ratio: number;
  stab_avg_offset_pct?: number;
  stab_max_offset_pct?: number;
  stab_p95_offset_pct?: number;
}

interface RenderResult {
  output_id: string;
  comparison_id?: string;
  stats: RenderStatsSummary;
}

export interface VideoListItem {
  video_id: string;
  filename: string;
  info: VideoInfo;
  thumbnail?: string | null;
  cached: boolean;
  output_count: number;
  source_bytes: number;
  output_bytes: number;
}

export interface RenderHistorySettings {
  mode: string;
  edit_mode: string;
  target_duration: number;
  trim_start: number;
  trim_end: number;
  min_speed: number;
  max_speed: number;
  sensitivity: number;
  smoothing: number;
  scale: number;
  output_fps: number;
  crf: number;
  output_aspect: string;
  auto_reframe: boolean;
  debug_overlay: boolean;
  include_audio: boolean;
  stabilize: boolean;
  stabilize_strength: number;
  stabilize_smoothness: number;
  stabilize_crop: number;
  use_feature_stabilize: boolean;
  feature_stabilize_weight: number;
  render_comparison: boolean;
  render_chapters: boolean;
}

export interface RenderHistoryItem {
  output_id: string;
  comparison_id?: string | null;
  video_id: string;
  video_hash?: string | null;
  video_filename?: string;
  created_at: number;
  stats: RenderStatsSummary;
  settings: RenderHistorySettings;
  output_bytes: number;
  comparison_bytes: number;
}

interface VideoMetaResult {
  video_id: string;
  filename: string;
  info: VideoInfo;
  thumbnails: string[];
  cached: boolean;
  output_count: number;
  source_bytes: number;
  output_bytes: number;
}

interface RenameVideoResult {
  video_id: string;
  filename: string;
}

export async function renderVideo(
  videoId: string,
  settings: Settings,
  pins: Pin[],
  keyframes: Keyframe[],
  onProgress: (progress: number, message: string) => void,
  signal?: AbortSignal,
): Promise<RenderResult | null> {
  const res = await fetch(`${API}/api/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      video_id: videoId,
      mode: settings.mode,
      edit_mode: settings.editMode,
      progress_action_blend: settings.progressActionBlend,
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      pins,
      keyframes,
      scale: settings.scale,
      output_fps: settings.outputFps,
      crf: settings.crf,
      output_aspect: settings.outputAspect,
      auto_reframe: settings.autoReframe,
      debug_overlay: settings.debugOverlay,
      stabilize: settings.stabilize,
      stabilize_strength: settings.stabilizeStrength,
      stabilize_smoothness: settings.stabilizeSmoothness,
      stabilize_crop: settings.stabilizeCrop,
      include_audio: settings.includeAudio,
      use_feature_stabilize: settings.useFeatureStabilize,
      feature_stabilize_weight: settings.featureStabilizeWeight,
      render_comparison: settings.renderComparison,
      render_chapters: settings.renderChapters,
    }),
  });

  if (!res.ok) throw new Error(await readErrorMessage(res));
  return consumeSseJson<RenderResult>(res, onProgress);
}

export async function listVideos(): Promise<VideoListItem[]> {
  const res = await fetch(`${API}/api/videos`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function getVideoMeta(videoId: string): Promise<VideoMetaResult> {
  const res = await fetch(`${API}/api/video-meta/${videoId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export interface DeleteVideoResult {
  video_id: string;
  deleted: boolean;
  deleted_outputs: number;
  deleted_bytes: number;
  deleted_output_bytes: number;
}

export interface LibraryStats {
  clips: number;
  outputs: number;
  clip_bytes: number;
  output_bytes: number;
  clip_outputs?: number;
  clip_output_bytes?: number;
}

export async function deleteVideo(videoId: string): Promise<DeleteVideoResult> {
  const res = await fetch(`${API}/api/videos/${videoId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function deleteAllVideos(): Promise<{
  deleted: number;
  video_ids: string[];
  deleted_outputs: number;
  deleted_bytes: number;
  deleted_output_bytes: number;
}> {
  const res = await fetch(`${API}/api/videos`, { method: "DELETE" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function deleteAllOutputs(): Promise<{ deleted_outputs: number; deleted_output_bytes: number }> {
  const res = await fetch(`${API}/api/outputs`, { method: "DELETE" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function deleteOutputsForVideo(videoId: string): Promise<{
  video_id: string;
  deleted_outputs: number;
  deleted_output_bytes: number;
}> {
  const res = await fetch(`${API}/api/outputs/${videoId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function getLibraryStats(videoId?: string): Promise<LibraryStats> {
  const url = videoId
    ? `${API}/api/library-stats?video_id=${encodeURIComponent(videoId)}`
    : `${API}/api/library-stats`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function listRenderHistory(videoId: string, limit: number = 150): Promise<RenderHistoryItem[]> {
  const params = new URLSearchParams();
  params.set("video_id", videoId);
  params.set("limit", String(limit));
  const res = await fetch(`${API}/api/renders?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export async function renameVideo(videoId: string, filename: string): Promise<RenameVideoResult> {
  const res = await fetch(`${API}/api/videos/${videoId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return res.json();
}

export function videoUrl(id: string) {
  return `${API}/api/video/${id}`;
}
