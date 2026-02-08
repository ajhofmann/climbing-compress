"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";
import { useTimeline } from "./use-timeline";
import { Tooltip } from "@/components/tooltip";

const THUMB_W = 160;
const THUMB_H = 90;
const MIN_PIN_RADIUS = 0.2;
const MAX_PIN_RADIUS = 10.0;

export function TimelineEditor() {
  const videoId = useStore((state) => state.videoId);
  const analysis = useStore((state) => state.analysis);
  const curve = useStore((state) => state.curve);
  const curveTimes = useStore((state) => state.curveTimes);
  const pins = useStore((state) => state.pins);
  const setPins = useStore((state) => state.setPins);
  const keyframes = useStore((state) => state.keyframes);
  const setKeyframes = useStore((state) => state.setKeyframes);
  const removeKeyframe = useStore((state) => state.removeKeyframe);
  const cruxPoints = useStore((state) => state.cruxPoints);
  const settings = useStore((state) => state.settings);
  const updateSettings = useStore((state) => state.updateSettings);
  const stats = useStore((state) => state.stats);

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
    minSpeed: settings.minSpeed,
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

  const applyCruxKeyframes = useCallback(() => {
    if (!analysis) return;
    const rangeStart = settings.trimStart;
    const rangeEnd = settings.trimEnd > 0 ? settings.trimEnd : analysis.duration;
    const inRangeCrux = cruxPoints
      .map((c) => c.time)
      .filter((t) => t >= rangeStart && t <= rangeEnd);

    const sampleSpeedAt = (time: number) => {
      if (!curve.length || !curveTimes.length) return 1.0;
      let bestIdx = 0;
      let bestDist = Number.POSITIVE_INFINITY;
      for (let i = 0; i < curveTimes.length; i++) {
        const d = Math.abs(curveTimes[i] - time);
        if (d < bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      return curve[bestIdx] ?? 1.0;
    };

    const rawTimes = [rangeStart, ...inRangeCrux, rangeEnd].sort((a, b) => a - b);
    const dedupedTimes: number[] = [];
    for (const t of rawTimes) {
      if (!dedupedTimes.length || Math.abs(t - dedupedTimes[dedupedTimes.length - 1]) > 0.2) {
        dedupedTimes.push(t);
      }
    }

    const generated = dedupedTimes.map((t, idx) => {
      let speed = sampleSpeedAt(t);
      if (idx > 0 && idx < dedupedTimes.length - 1) {
        speed = Math.max(settings.minSpeed, Math.min(settings.maxSpeed, speed * 0.78));
      } else {
        speed = Math.max(0.9, Math.min(settings.maxSpeed, speed));
      }
      return { time: Number(t.toFixed(2)), speed: Number(speed.toFixed(2)) };
    });

    setKeyframes(generated);
    updateSettings({ editMode: "keyframes" });
  }, [analysis, settings, cruxPoints, curve, curveTimes, setKeyframes, updateSettings]);

  const applyCruxPins = useCallback(() => {
    if (!analysis) return;
    const rangeStart = settings.trimStart;
    const rangeEnd = settings.trimEnd > 0 ? settings.trimEnd : analysis.duration;
    const inRangeCrux = cruxPoints
      .map((c) => c.time)
      .filter((t) => t >= rangeStart && t <= rangeEnd);
    if (inRangeCrux.length === 0) return;

    const sampleSpeedAt = (time: number) => {
      if (!curve.length || !curveTimes.length) return Math.max(settings.minSpeed, 1.0);
      let bestIdx = 0;
      let bestDist = Number.POSITIVE_INFINITY;
      for (let i = 0; i < curveTimes.length; i++) {
        const d = Math.abs(curveTimes[i] - time);
        if (d < bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      return curve[bestIdx] ?? Math.max(settings.minSpeed, 1.0);
    };

    const dedupedTimes: number[] = [];
    for (const t of [...inRangeCrux].sort((a, b) => a - b)) {
      if (!dedupedTimes.length || Math.abs(t - dedupedTimes[dedupedTimes.length - 1]) > 0.2) {
        dedupedTimes.push(t);
      }
    }

    const generated = dedupedTimes.map((t) => {
      const speed = Math.max(
        settings.minSpeed,
        Math.min(settings.maxSpeed, sampleSpeedAt(t) * 0.8),
      );
      return {
        time: Number(t.toFixed(2)),
        speed: Number(speed.toFixed(2)),
        radius: 1.2,
      };
    });

    setPins(generated);
    updateSettings({ editMode: "pins" });
  }, [analysis, settings, cruxPoints, curve, curveTimes, setPins, updateSettings]);

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
          <span>del to delete hovered</span>
          <span>arrows to nudge hovered</span>
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
          {settings.editMode === "pins" && cruxPoints.length > 0 && (
            <Tooltip text="Auto-generate speed pins at detected crux markers in the current trim range">
              <button
                onClick={applyCruxPins}
                className="text-neon-magenta hover:underline"
              >
                from crux
              </button>
            </Tooltip>
          )}
          {settings.editMode === "keyframes" && cruxPoints.length > 0 && (
            <Tooltip text="Auto-generate keyframes from detected crux markers in the current trim range">
              <button
                onClick={applyCruxKeyframes}
                className="text-neon-magenta hover:underline"
              >
                from crux
              </button>
            </Tooltip>
          )}
        </div>
      </div>
      <div className="relative">
        <canvas
          ref={canvasRef}
          {...handlers}
          tabIndex={0}
          aria-label={`Speed curve editor (${settings.editMode}) — click to add, drag to move, right-click/Delete to remove, arrow keys to nudge hovered point${settings.editMode === "pins" ? ", scroll to resize pin radius" : ""}`}
          role="img"
          className="w-full h-44 rounded-lg border border-border focus:outline-none focus:ring-1 focus:ring-accent/60"
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
                  min={settings.minSpeed}
                  max={settings.maxSpeed}
                  step={0.05}
                  className="w-[4.5rem] px-1 py-0.5 bg-bg-input border border-border rounded"
                  onChange={(e) => {
                    const s = Math.max(settings.minSpeed, Math.min(settings.maxSpeed, Number(e.target.value)));
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

      {settings.editMode === "pins" && pins.length > 0 && (
        <div className="rounded border border-border p-2 flex flex-col gap-1">
          <div className="text-[10px] font-pixel uppercase tracking-wider text-text-muted">pin values</div>
          <div className="grid gap-1">
            {pins.map((pin, idx) => (
              <div key={`${idx}-${pin.time.toFixed(3)}-${pin.speed.toFixed(3)}-${(pin.radius ?? 2).toFixed(3)}`} className="flex items-center gap-2 text-[10px]">
                <span className="text-text-muted w-8">#{idx + 1}</span>
                <label className="text-text-muted">t</label>
                <input
                  type="number"
                  value={Number(pin.time.toFixed(2))}
                  min={0}
                  max={analysis.duration}
                  step={0.1}
                  className="w-[4.5rem] px-1 py-0.5 bg-bg-input border border-border rounded"
                  onChange={(e) => {
                    const t = Math.max(0, Math.min(analysis.duration, Number(e.target.value)));
                    const next = [...pins];
                    next[idx] = { ...next[idx], time: Number.isFinite(t) ? t : next[idx].time };
                    setPins(next);
                  }}
                />
                <label className="text-text-muted">spd</label>
                <input
                  type="number"
                  value={Number(pin.speed.toFixed(2))}
                  min={settings.minSpeed}
                  max={settings.maxSpeed}
                  step={0.05}
                  className="w-[4.5rem] px-1 py-0.5 bg-bg-input border border-border rounded"
                  onChange={(e) => {
                    const s = Math.max(settings.minSpeed, Math.min(settings.maxSpeed, Number(e.target.value)));
                    const next = [...pins];
                    next[idx] = { ...next[idx], speed: Number.isFinite(s) ? s : next[idx].speed };
                    setPins(next);
                  }}
                />
                <label className="text-text-muted">r</label>
                <input
                  type="number"
                  value={Number((pin.radius ?? 2).toFixed(2))}
                  min={MIN_PIN_RADIUS}
                  max={MAX_PIN_RADIUS}
                  step={0.1}
                  className="w-[4.5rem] px-1 py-0.5 bg-bg-input border border-border rounded"
                  onChange={(e) => {
                    const r = Math.max(MIN_PIN_RADIUS, Math.min(MAX_PIN_RADIUS, Number(e.target.value)));
                    const next = [...pins];
                    next[idx] = { ...next[idx], radius: Number.isFinite(r) ? r : (next[idx].radius ?? 2) };
                    setPins(next);
                  }}
                />
                <button
                  onClick={() => setPins(pins.filter((_, i) => i !== idx))}
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
