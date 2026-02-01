"use client";

import { useStore } from "@/lib/store";
import { useTimeline } from "./use-timeline";

export function TimelineEditor() {
  const { analysis, curve, curveTimes, pins, setPins, settings, updateSettings, stats } = useStore();

  const waveformUrl = analysis
    ? (settings.mode === "progress" ? analysis.waveform_progress : analysis.waveform_action)
    : "";

  const { canvasRef, handlers } = useTimeline({
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

  if (!analysis) {
    return (
      <div className="rounded-xl bg-bg-card border border-border flex items-center justify-center h-44 text-text-muted text-sm">
        run analyze to see the speed curve editor
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center px-1">
        <span className="text-xs font-medium text-text">speed curve editor</span>
        <div className="flex gap-3 text-[10px] text-text-muted">
          <span>click to add point</span>
          <span>drag to adjust</span>
          <span>right-click to delete</span>
          {pins.length > 0 && (
            <button onClick={() => setPins([])} className="text-danger hover:underline">
              clear all
            </button>
          )}
        </div>
      </div>
      <canvas
        ref={canvasRef}
        {...handlers}
        className="w-full h-44 rounded-lg border border-border"
      />
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
    </div>
  );
}
