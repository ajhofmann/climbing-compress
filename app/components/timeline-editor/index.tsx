"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";
import { useTimeline } from "./use-timeline";
import { Tooltip } from "@/components/tooltip";

const THUMB_W = 160;
const THUMB_H = 90;

export function TimelineEditor() {
  const { videoId, analysis, curve, curveTimes, pins, setPins, settings, updateSettings, stats } = useStore();

  const waveformUrl = analysis
    ? (settings.mode === "progress" ? analysis.waveform_progress : analysis.waveform_action)
    : "";

  // Frame preview state
  const previewVideoRef = useRef<HTMLVideoElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const [previewPos, setPreviewPos] = useState<{ x: number; time: number } | null>(null);
  const [previewReady, setPreviewReady] = useState(false);
  const seekingRef = useRef(false);

  const { canvasRef, handlers: baseHandlers } = useTimeline({
    duration: analysis?.duration ?? 60,
    maxSpeed: settings.maxSpeed,
    curve,
    curveTimes,
    pins,
    waveformUrl,
    onPinsChange: setPins,
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
    setPreviewPos({ x, time });

    // Seek the hidden video (throttled by seekingRef)
    const vid = previewVideoRef.current;
    if (vid && !seekingRef.current && Math.abs(vid.currentTime - time) > 0.1) {
      seekingRef.current = true;
      vid.currentTime = time;
    }
  }, [baseHandlers, analysis, canvasRef]);

  const onMouseLeave = useCallback((_e: React.MouseEvent) => {
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
      (canvasRef.current?.getBoundingClientRect().width ?? 600) - THUMB_W)),
    bottom: "100%",
    marginBottom: 8,
  } : undefined;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center px-1">
        <span className="text-xs font-medium text-text">speed curve editor</span>
        <div className="flex gap-3 text-[10px] text-text-muted">
          <span>click to add</span>
          <span>drag to move</span>
          <span>scroll to resize</span>
          <span>right-click to delete</span>
          {pins.length > 0 && (
            <Tooltip text="Remove all speed pins from the timeline">
              <button onClick={() => setPins([])} className="text-danger hover:underline">
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
          aria-label="Speed curve editor — click to add pins, drag to move, scroll to resize, right-click to delete"
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
