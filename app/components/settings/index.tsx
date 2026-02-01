"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { Settings, DEFAULT_SETTINGS, PRESETS } from "@/lib/types";

function Slider({ label, emoji, info, value, min, max, step, onChange }: {
  label: string; emoji?: string; info?: string; value: number;
  min: number; max: number; step: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5 flex-1 min-w-[160px]">
      <div className="flex justify-between items-baseline">
        <span className="text-xs font-semibold text-text">
          {emoji && <span className="mr-1">{emoji}</span>}
          {label}
        </span>
        <span className="text-xs font-mono text-accent font-bold">{value}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
      {info && <span className="text-[10px] text-text-muted leading-tight">{info}</span>}
    </label>
  );
}

function Section({ title, emoji, children, defaultOpen = false }: {
  title: string; emoji?: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-border rounded-xl overflow-hidden bg-bg-card/50">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 text-left text-sm font-medium text-text flex justify-between items-center hover:bg-bg-card transition-colors"
      >
        <span>{emoji && <span className="mr-2">{emoji}</span>}{title}</span>
        <span className={`text-text-muted text-xs transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
      </button>
      {open && <div className="px-4 pb-4 pt-2 border-t border-border">{children}</div>}
    </div>
  );
}

function PhaseLabel({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="flex items-center gap-2 pt-2 pb-0.5">
      <span className="text-[10px] font-bold uppercase tracking-widest text-accent">{label}</span>
      <span className="text-[10px] text-text-muted">{detail}</span>
      <div className="flex-1 border-t border-border/50" />
    </div>
  );
}

export function SettingsPanel() {
  const { settings, updateSettings } = useStore();
  const s = settings;
  const u = (k: keyof Settings, v: any) => updateSettings({ [k]: v });

  const applyPreset = (overrides: Partial<Settings>) => {
    updateSettings({ ...DEFAULT_SETTINGS, ...overrides, trimStart: s.trimStart, trimEnd: s.trimEnd, analyzeStride: s.analyzeStride });
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Presets */}
      <div className="flex gap-1.5 flex-wrap">
        {PRESETS.map((p) => (
          <button
            key={p.name}
            onClick={() => applyPreset(p.overrides)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-border hover:border-accent hover:bg-accent/10 transition-all text-text-muted hover:text-text"
            title={p.desc}
          >
            <span className="mr-1">{p.emoji}</span>
            {p.name}
          </button>
        ))}
      </div>

      <PhaseLabel label="Speed Curve" detail="instant preview" />

      {/* Mode toggle */}
      <div className="flex gap-1 p-1 bg-bg-card rounded-xl">
        {([
          { key: "progress" as const, label: "Constant Progress", emoji: "🏔️", desc: "smooth journey up the wall" },
          { key: "action" as const, label: "Action Highlight", emoji: "⚡", desc: "slow-mo on big moves" },
        ]).map(({ key, label, emoji }) => (
          <button
            key={key}
            onClick={() => u("mode", key)}
            className={`flex-1 py-2.5 px-3 rounded-lg text-sm font-semibold transition-all ${
              s.mode === key
                ? "bg-accent text-white shadow-md"
                : "text-text-muted hover:text-text hover:bg-bg-input"
            }`}
          >
            <span className="mr-1.5">{emoji}</span>
            {label}
          </button>
        ))}
      </div>
      <p className="text-[11px] text-text-muted -mt-1 px-1">
        {s.mode === "progress"
          ? "at 50% of the video, you're 50% up the boulder. stalling = fast forward, moving = real time."
          : "big moves get slow-mo, chalk-ups get skipped. classic climbing edit style."}
      </p>

      {/* Main sliders */}
      <div className="flex gap-5 flex-wrap">
        <Slider emoji="⏱" label="Duration" info="target output length" value={s.targetDuration} min={3} max={120} step={1} onChange={(v) => u("targetDuration", v)} />
        <Slider emoji="🎯" label="Sensitivity" info="lower = more generous slow-mo" value={s.sensitivity} min={0.01} max={0.99} step={0.01} onChange={(v) => u("sensitivity", v)} />
        <Slider emoji="⏩" label="Max Speed" info="how fast to skip rest" value={s.maxSpeed} min={1} max={30} step={0.5} onChange={(v) => u("maxSpeed", v)} />
      </div>

      {/* Advanced */}
      <Section emoji="🎛" title="Speed Curve">
        <div className="flex gap-5 flex-wrap">
          <Slider label="Min Speed" info="0.05 = 20x slow-mo" value={s.minSpeed} min={0.05} max={1} step={0.01} onChange={(v) => u("minSpeed", v)} />
          {s.mode === "action" && (
            <Slider label="Steepness" info="sharp vs gradual transitions" value={s.steepness} min={1} max={50} step={1} onChange={(v) => u("steepness", v)} />
          )}
          <Slider label="Smoothing" info="seconds of curve blur" value={s.smoothing} min={0.05} max={2} step={0.05} onChange={(v) => u("smoothing", v)} />
          {s.mode === "progress" && (
            <Slider label="Floor" info="higher = less aggressive skip on stalls" value={s.progressFloor} min={0.001} max={0.3} step={0.001} onChange={(v) => u("progressFloor", v)} />
          )}
        </div>
      </Section>

      {s.mode === "action" && (
        <Section emoji="🦎" title="Body Part Weights">
          <div className="flex gap-5 flex-wrap">
            <Slider label="Hands" info="reaching for holds" value={s.handWeight} min={0} max={10} step={0.1} onChange={(v) => u("handWeight", v)} />
            <Slider label="Feet" info="foot placements" value={s.footWeight} min={0} max={10} step={0.1} onChange={(v) => u("footWeight", v)} />
            <Slider label="Core" info="dyno detector 🚀" value={s.coreWeight} min={0} max={20} step={0.1} onChange={(v) => u("coreWeight", v)} />
          </div>
        </Section>
      )}

      <PhaseLabel label="Render" detail="re-render to apply" />

      <Section emoji="📐" title="Stabilization" defaultOpen={true}>
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2 text-xs text-text cursor-pointer">
            <input type="checkbox" checked={s.stabilize} onChange={(e) => u("stabilize", e.target.checked)}
              className="accent-accent w-4 h-4 rounded" />
            <span className="font-semibold">enable pose-anchored stabilization</span>
          </label>
          {s.stabilize && (
            <>
              <p className="text-[10px] text-text-muted leading-tight -mt-1">
                locks the camera onto the climber&apos;s body. higher crop = more room to correct shake.
              </p>
              <div className="flex gap-5 flex-wrap">
                <Slider label="Strength" info="0 = off, 1 = full gimbal lock" value={s.stabilizeStrength} min={0} max={1} step={0.01} onChange={(v) => u("stabilizeStrength", v)} />
                <Slider label="Smoothness" info="seconds of trajectory smoothing" value={s.stabilizeSmoothness} min={0.1} max={5} step={0.1} onChange={(v) => u("stabilizeSmoothness", v)} />
                <Slider label="Crop" info="frame sacrificed for shake room" value={s.stabilizeCrop} min={0.01} max={0.5} step={0.01} onChange={(v) => u("stabilizeCrop", v)} />
              </div>
            </>
          )}
        </div>
      </Section>

      <Section emoji="🎥" title="Export Quality">
        <div className="flex gap-5 flex-wrap items-end">
          <Slider label="Resolution" info="0.25 = tiny preview, 1.0 = full res" value={s.scale} min={0.1} max={1} step={0.05} onChange={(v) => u("scale", v)} />
          <Slider label="Quality" info="lower = sharper, bigger file" value={s.crf} min={10} max={40} step={1} onChange={(v) => u("crf", v)} />
          <label className="flex flex-col gap-1.5 flex-1 min-w-[120px]">
            <span className="text-xs font-semibold text-text">FPS</span>
            <select value={s.outputFps} onChange={(e) => u("outputFps", parseInt(e.target.value))}
              className="bg-bg-input border border-border rounded-lg px-3 py-1.5 text-sm text-text">
              <option value={24}>24 (cinematic)</option>
              <option value={30}>30 (standard)</option>
              <option value={60}>60 (smooth)</option>
            </select>
          </label>
        </div>
        <label className="flex items-center gap-2 mt-3 text-xs text-text-muted cursor-pointer">
          <input type="checkbox" checked={s.debugOverlay} onChange={(e) => u("debugOverlay", e.target.checked)}
            className="accent-accent w-4 h-4 rounded" />
          show debug overlay (skeleton + speed badge)
        </label>
      </Section>

      <PhaseLabel label="Analysis" detail="re-analyze to apply" />

      <Section emoji="🔬" title="Analysis">
        <div className="flex gap-5 flex-wrap items-end">
          <label className="flex flex-col gap-1.5 flex-1 min-w-[160px]">
            <div className="flex justify-between items-baseline">
              <span className="text-xs font-semibold text-text">Detection Quality</span>
              <span className="text-xs font-mono text-accent font-bold">
                {s.analyzeStride === 1 ? "high" : s.analyzeStride === 2 ? "balanced" : "fast"}
              </span>
            </div>
            <select value={s.analyzeStride} onChange={(e) => u("analyzeStride", parseInt(e.target.value))}
              className="bg-bg-input border border-border rounded-lg px-3 py-1.5 text-sm text-text">
              <option value={1}>every frame (slow, best tracking)</option>
              <option value={2}>every 2nd frame (default)</option>
              <option value={3}>every 3rd frame (fast, rougher)</option>
            </select>
            <span className="text-[10px] text-text-muted leading-tight">re-analyze after changing</span>
          </label>
        </div>
      </Section>
    </div>
  );
}
