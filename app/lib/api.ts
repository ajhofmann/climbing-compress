import { Pin, Settings, SolveResult } from "./types";

const API = "http://localhost:8000";

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
) {
  const res = await fetch(`${API}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_id: videoId, stride, force }),
  });

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let result: any = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        onProgress(data.progress, data.message);
        if (data.done) result = data;
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
      pins,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function renderVideo(
  videoId: string,
  settings: Settings,
  pins: Pin[],
  onProgress: (progress: number, message: string) => void,
) {
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
      pins,
      scale: settings.scale,
      output_fps: settings.outputFps,
      crf: settings.crf,
      debug_overlay: settings.debugOverlay,
    }),
  });

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let result: any = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        onProgress(data.progress, data.message);
        if (data.done) result = data;
      }
    }
  }
  return result;
}

export function videoUrl(id: string) {
  return `${API}/api/video/${id}`;
}
