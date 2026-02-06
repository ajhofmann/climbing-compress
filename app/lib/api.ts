import { AnalysisData, Pin, Settings, SolveResult, Project, Metrics, JobRecord, ProjectSummary } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadVideo(file: File, projectId?: string | null) {
  const form = new FormData();
  form.append("file", file);
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await fetch(`${API}/api/upload${query}`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listVideos(projectId?: string | null) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await fetch(`${API}/api/videos${query}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API}/api/projects`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createProject(name: string, description?: string): Promise<Project> {
  const res = await fetch(`${API}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateProject(projectId: string, name?: string, description?: string): Promise<Project> {
  const res = await fetch(`${API}/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getProjectSummary(projectId: string): Promise<ProjectSummary> {
  const res = await fetch(`${API}/api/projects/${projectId}/summary`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteProject(projectId: string): Promise<{ id: string; deleted: boolean }> {
  const res = await fetch(`${API}/api/projects/${projectId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function assignVideoProject(videoId: string, projectId: string | null) {
  const res = await fetch(`${API}/api/videos/${videoId}/project`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMetrics(): Promise<Metrics> {
  const res = await fetch(`${API}/api/metrics`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listJobs(projectId?: string | null): Promise<JobRecord[]> {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await fetch(`${API}/api/jobs${query}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJob(jobId: string): Promise<JobRecord> {
  const res = await fetch(`${API}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function cancelJob(jobId: string): Promise<{ id: string; status: string }> {
  const res = await fetch(`${API}/api/jobs/${jobId}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function retryJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API}/api/jobs/${jobId}/retry`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listOutputs(videoId?: string | null, projectId?: string | null) {
  const params = new URLSearchParams();
  if (videoId) params.set("video_id", videoId);
  if (projectId) params.set("project_id", projectId);
  const query = params.toString();
  const res = await fetch(`${API}/api/outputs${query ? `?${query}` : ""}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function awaitJobResult(
  jobId: string,
  onProgress: (progress: number, message: string) => void,
  pollMs: number = 1000,
) {
  while (true) {
    const job = await getJob(jobId);
    onProgress(job.progress ?? 0, job.message ?? "");
    if (job.status === "success") return job.result;
    if (job.status === "failed") throw new Error(job.message ?? "Job failed");
    if (job.status === "cancelled") throw new Error("Job cancelled");
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
}

export async function enqueueAnalyze(
  videoId: string,
  settings: Settings,
  force: boolean,
) {
  const res = await fetch(`${API}/api/jobs/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_id: videoId,
      stride: settings.analyzeStride,
      force,
      use_tracker: settings.useTracker,
      use_flow: settings.useFlow,
      tracker_model: settings.trackerModel,
      climber_strategy: settings.climberStrategy,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function enqueueRender(
  videoId: string,
  settings: Settings,
  pins: Pin[],
) {
  const res = await fetch(`${API}/api/jobs/render`, {
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      highlight_action_weight: settings.highlightActionWeight,
      highlight_progress_weight: settings.highlightProgressWeight,
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
      render_comparison: settings.renderComparison,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function enqueuePreview(
  videoId: string,
  settings: Settings,
  pins: Pin[],
  previewStart: number,
  previewDuration: number,
  options?: { scale?: number; fps?: number; crf?: number; debugOverlay?: boolean },
) {
  const res = await fetch(`${API}/api/jobs/preview`, {
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      highlight_action_weight: settings.highlightActionWeight,
      highlight_progress_weight: settings.highlightProgressWeight,
      pins,
      scale: settings.scale,
      output_fps: settings.outputFps,
      crf: settings.crf,
      debug_overlay: settings.debugOverlay,
      stabilize: settings.stabilize,
      stabilize_strength: settings.stabilizeStrength,
      stabilize_smoothness: settings.stabilizeSmoothness,
      stabilize_crop: settings.stabilizeCrop,
      include_audio: false,
      use_feature_stabilize: settings.useFeatureStabilize,
      feature_stabilize_weight: settings.featureStabilizeWeight,
      render_comparison: false,
      preview_start: previewStart,
      preview_duration: previewDuration,
      preview_scale: options?.scale ?? 0.35,
      preview_fps: options?.fps ?? 24,
      preview_crf: options?.crf ?? 28,
      preview_debug_overlay: options?.debugOverlay ?? false,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
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
  climberStrategy: string = "auto",
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
      tracker_model: trackerModel,
      climber_strategy: climberStrategy,
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      highlight_action_weight: settings.highlightActionWeight,
      highlight_progress_weight: settings.highlightProgressWeight,
      pins,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

interface RenderResult {
  output_id: string;
  comparison_id?: string;
  stats: {
    output_duration: number;
    speed_min: number;
    speed_max: number;
    slow_pct: number;
    action_rest_ratio: number;
  };
}

interface PreviewResult {
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      highlight_action_weight: settings.highlightActionWeight,
      highlight_progress_weight: settings.highlightProgressWeight,
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
      render_comparison: settings.renderComparison,
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

export async function previewVideo(
  videoId: string,
  settings: Settings,
  pins: Pin[],
  previewStart: number,
  previewDuration: number,
  onProgress: (progress: number, message: string) => void,
  options?: { scale?: number; fps?: number; crf?: number; debugOverlay?: boolean },
): Promise<PreviewResult | null> {
  const res = await fetch(`${API}/api/preview`, {
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
      down_weight: settings.downWeight,
      rest_threshold_s: settings.restThreshold,
      trim_start: settings.trimStart,
      trim_end: settings.trimEnd,
      highlight_action_weight: settings.highlightActionWeight,
      highlight_progress_weight: settings.highlightProgressWeight,
      pins,
      scale: settings.scale,
      output_fps: settings.outputFps,
      crf: settings.crf,
      debug_overlay: settings.debugOverlay,
      stabilize: settings.stabilize,
      stabilize_strength: settings.stabilizeStrength,
      stabilize_smoothness: settings.stabilizeSmoothness,
      stabilize_crop: settings.stabilizeCrop,
      include_audio: false,
      use_feature_stabilize: settings.useFeatureStabilize,
      feature_stabilize_weight: settings.featureStabilizeWeight,
      render_comparison: false,
      preview_start: previewStart,
      preview_duration: previewDuration,
      preview_scale: options?.scale ?? 0.35,
      preview_fps: options?.fps ?? 24,
      preview_crf: options?.crf ?? 28,
      preview_debug_overlay: options?.debugOverlay ?? false,
    }),
  });

  if (!res.ok) throw new Error(await res.text());
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let result: PreviewResult | null = null;

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
