"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";
import { useTimeline } from "./use-timeline";
import { Tooltip } from "@/components/tooltip";

const THUMB_W = 160;
const THUMB_H = 90;

export function TimelineEditor() {
  const {
    videoId, analysis, curve, curveTimes,
    pins, setPins,
    keyframes, setKeyframes, removeKeyframe,
    cruxPoints, settings, updateSettings, stats,
  } = useStore();

  const waveformUrl = analysis
    ? (
      settings.mode === "progress"
        ? analysis.waveform_progress
        : settings.mode === "action"
          ? analysis.waveform_action
          : (settings.progressActionBlend < 0.5 ? analysis.waveform_progress : analysis.waveform_action)
    )
    : "";

  // Frame preview state
  const previewVideoRef = useRef<HTMLVideoElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const [previewPos, setPreviewPos] = useState<{ x: number; time: number; width: number } | null>(null);
  const [previewReady, setPreviewReady] = useState(false);
  const seekingRef = useRef(false);

  const { canvasRef, handlers: baseHandlers } = useTimeline({
    duration: analysis?.duration ?? 60,
    maxSpeed: settings.maxSpeed,
    curve,
    curveTimes,
    editMode: settings.editMode,
    pins,
    keyframes,
    cruxPoints,
    waveformUrl,
    onPinsChange: setPins,
    onKeyframesChange: setKeyframes,
    trimStart: settings.trimStart,
    trimEnd: settings.trimEnd,
    onTrimChange: (start, end) => updateSettings({ trimStart: start, trimEnd: end }),
  });

  // Seek the hidden video on hover and capture frame to preview canvas
  const captureFrame = useCallback(() => {
    const vid = previewVideoRef.current;
    const cvs = previewCanvasRef.current;
    if (!vid || !cvs || vid.readyState < 2) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(vid, 0, 0, THUMB_W, THUMB_H);
    setPreviewReady(true);
    seekingRef.current = false;
  }, []);

  useEffect(() => {
    const vid = previewVideoRef.current;
    if (!vid) return;
    vid.addEventListener("seeked", captureFrame);
    return () => vid.removeEventListener("seeked", captureFrame);
  }, [captureFrame]);

  // Wrap mouse handlers to track hover position for preview
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    baseHandlers.onMouseMove(e);
    if (!analysis || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const time = Math.max(0, Math.min(analysis.duration, (x / rect.width) * analysis.duration));
    setPreviewPos({ x, time, width: rect.width });

    // Seek the hidden video (throttled by seekingRef)
    const vid = previewVideoRef.current;
    if (vid && !seekingRef.current && Math.abs(vid.currentTime - time) > 0.1) {
      seekingRef.current = true;
      vid.currentTime = time;
    }
  }, [baseHandlers, analysis, canvasRef]);

  const onMouseLeave = useCallback(() => {
    baseHandlers.onMouseLeave();
    setPreviewPos(null);
    setPreviewReady(false);
  }, [baseHandlers]);

  const handlers = { ...baseHandlers, onMouseMove, onMouseLeave };

  if (!analysis) {
    return (
      <div className="rounded-lg bg-bg-card border border-border flex items-center justify-center h-24 text-text-muted text-xs font-pixel uppercase tracking-wider opacity-60">
        run analyze to see the speed curve editor
      </div>
    );
  }

  // Compute preview tooltip position (above cursor, clamped to canvas bounds)
  const previewStyle: React.CSSProperties | undefined = previewPos ? {
    left: Math.max(0, Math.min(previewPos.x - THUMB_W / 2,
      previewPos.width - THUMB_W)),
    bottom: "100%",
    marginBottom: 8,
  } : undefined;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center px-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text">speed curve editor</span>
          <div className="flex rounded border border-border overflow-hidden">
            <button
              onClick={() => updateSettings({ editMode: "pins" })}
              className={`px-2 py-0.5 text-[10px] font-pixel uppercase ${settings.editMode === "pins" ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text"}`}
            >
              pins
            </button>
            <button
              onClick={() => updateSettings({ editMode: "keyframes" })}
              className={`px-2 py-0.5 text-[10px] font-pixel uppercase border-l border-border ${settings.editMode === "keyframes" ? "bg-warm/15 text-warm" : "text-text-muted hover:text-text"}`}
            >
              keyframes
            </button>
          </div>
        </div>
        <div className="flex gap-3 text-[10px] text-text-muted">
          <span>click to add</span>
          <span>drag to move</span>
          {settings.editMode === "pins" && <span>scroll to resize</span>}
          <span>right-click to delete</span>
          {cruxPoints.length > 0 && <span className="text-neon-magenta">crux: {cruxPoints.length}</span>}
          {(settings.editMode === "pins" ? pins.length > 0 : keyframes.length > 0) && (
            <Tooltip text={settings.editMode === "pins" ? "Remove all speed pins from the timeline" : "Remove all keyframes from the timeline"}>
              <button
                onClick={() => settings.editMode === "pins" ? setPins([]) : setKeyframes([])}
                className="text-danger hover:underline"
              >
                clear all
              </button>
            </Tooltip>
          )}
        </div>
      </div>
      <div className="relative">
        <canvas
          ref={canvasRef}
          {...handlers}
          aria-label={`Speed curve editor (${settings.editMode}) — click to add, drag to move, right-click to delete${settings.editMode === "pins" ? ", scroll to resize pin radius" : ""}`}
          role="img"
          className="w-full h-44 rounded-lg border border-border"
        />
        {/* Frame preview tooltip */}
        {previewPos && previewReady && (
          <div
            className="absolute pointer-events-none"
            style={previewStyle}
          >
            <div className="rounded-lg overflow-hidden shadow-xl border border-border/60 bg-bg-card-solid">
              <canvas ref={previewCanvasRef} width={THUMB_W} height={THUMB_H} className="block" />
              <div className="text-center text-[10px] font-mono text-text-muted py-0.5 bg-bg-card-solid/90">
                {previewPos.time.toFixed(1)}s
              </div>
            </div>
          </div>
        )}
      </div>
      <div className="flex justify-between px-1 text-[10px] text-text-muted">
        <span>0s</span>
        <span className="font-mono" style={{ color: "var(--warm)" }}>
          trim: {settings.trimStart.toFixed(1)}s – {(settings.trimEnd > 0 ? settings.trimEnd : analysis.duration).toFixed(1)}s
          {" "}({((settings.trimEnd > 0 ? settings.trimEnd : analysis.duration) - settings.trimStart).toFixed(1)}s)
        </span>
        {stats && (
          <span className="font-mono">
            output: {stats.output_duration}s
          </span>
        )}
        <span>{analysis.duration.toFixed(0)}s</span>
      </div>

      {settings.editMode === "keyframes" && keyframes.length > 0 && (
        <div className="rounded border border-border p-2 flex flex-col gap-1">
          <div className="text-[10px] font-pixel uppercase tracking-wider text-text-muted">keyframe values</div>
          <div className="grid gap-1">
            {keyframes.map((kf, idx) => (
              <div key={`${idx}-${kf.time.toFixed(3)}-${kf.speed.toFixed(3)}`} className="flex items-center gap-2 text-[10px]">
                <span className="text-text-muted w-8">#{idx + 1}</span>
                <label className="text-text-muted">t</label>
                <input
                  type="number"
                  value={Number(kf.time.toFixed(2))}
                  min={0}
                  max={analysis.duration}
                  step={0.1}
                  className="w-[4.5rem] px-1 py-0.5 bg-bg-input border border-border rounded"
                  onChange={(e) => {
                    const t = Math.max(0, Math.min(analysis.duration, Number(e.target.value)));
                    const next = [...keyframes];
                    next[idx] = { ...next[idx], time: Number.isFinite(t) ? t : next[idx].time };
                    setKeyframes(next);
                  }}
                />
                <label className="text-text-muted">spd</label>
                <input
                  type="number"
                  value={Number(kf.speed.toFixed(2))}
                  min={0.1}
                  max={settings.maxSpeed}
                  step={0.05}
                  className="w-[4.5rem] px-1 py-0.5 bg-bg-input border border-border rounded"
                  onChange={(e) => {
                    const s = Math.max(0.1, Math.min(settings.maxSpeed, Number(e.target.value)));
                    const next = [...keyframes];
                    next[idx] = { ...next[idx], speed: Number.isFinite(s) ? s : next[idx].speed };
                    setKeyframes(next);
                  }}
                />
                <button
                  onClick={() => removeKeyframe(idx)}
                  className="text-danger hover:underline ml-auto"
                >
                  delete
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hidden video for frame capture */}
      {videoId && (
        <video
          ref={previewVideoRef}
          src={videoUrl(videoId)}
          preload="auto"
          muted
          playsInline
          className="hidden"
        />
      )}
    </div>
  );
}
