"use client";

import { useStore } from "@/lib/store";

const CLIMBING_MESSAGES = [
  "chalking up...",
  "reading the sequence...",
  "finding the beta...",
  "sending it...",
  "crimping hard...",
  "matching feet...",
  "flagging for balance...",
  "heel hooking...",
];

export function ProgressBar() {
  const { isAnalyzing, isRendering, progress, progressMessage } = useStore();
  const active = isAnalyzing || isRendering;

  if (!active && !progressMessage) return null;

  const pct = Math.max(progress * 100, 1);
  const funMsg = active && progress > 0.1 && progress < 0.9
    ? CLIMBING_MESSAGES[Math.floor(progress * CLIMBING_MESSAGES.length) % CLIMBING_MESSAGES.length]
    : null;

  return (
    <div className="w-full flex flex-col gap-1.5">
      {active && (
        <div className="w-full h-2.5 bg-bg-card rounded-full overflow-hidden border border-border">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              progress < 1 ? "progress-shimmer" : "bg-accent"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      <div className="flex justify-between items-center">
        <p className="text-xs text-text-muted">
          {progressMessage}
          {funMsg && <span className="ml-2 text-accent-light italic">{funMsg}</span>}
        </p>
        {active && (
          <span className="text-xs font-mono text-text-muted">{Math.round(pct)}%</span>
        )}
      </div>
    </div>
  );
}
