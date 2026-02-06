"use client";

import { useStore } from "@/lib/store";

const CLIMBING_MESSAGES = [
  "CHALKING UP...",
  "READING THE SEQUENCE...",
  "FINDING THE BETA...",
  "SENDING IT...",
  "CRIMPING HARD...",
  "MATCHING FEET...",
  "FLAGGING FOR BALANCE...",
  "HEEL HOOKING...",
];

export function ProgressBar() {
  const { isAnalyzing, isRendering, isPreviewing, progress, progressMessage } = useStore();
  const active = isAnalyzing || isRendering || isPreviewing;

  if (!active && !progressMessage) return null;

  const pct = Math.max(progress * 100, 0);
  const funMsg = active && progress > 0.1 && progress < 0.9
    ? CLIMBING_MESSAGES[Math.floor(progress * CLIMBING_MESSAGES.length) % CLIMBING_MESSAGES.length]
    : null;

  return (
    <div className="w-full flex flex-col gap-1">
      {active && (
        <div className="flex items-center gap-2">
          {/* LED segment bar */}
          <div className="flex gap-[2px] h-2 flex-1">
            {Array.from({ length: 16 }).map((_, i) => {
              const lit = i < Math.floor(progress * 16);
              const ratio = i / 16;
              const color = ratio < 0.5 ? "var(--neon-cyan)" : ratio < 0.75 ? "var(--neon-lime)" : "var(--neon-orange)";
              return (
                <div
                  key={i}
                  className="flex-1 rounded-[1px]"
                  style={{
                    background: lit ? color : "#1a1a2e",
                    boxShadow: lit ? `0 0 3px ${color}` : "none",
                    opacity: lit ? 1 : 0.25,
                    transition: "all 0.15s",
                  }}
                />
              );
            })}
          </div>
          <span className="text-xs font-retro led-text tabular-nums shrink-0">{Math.round(pct)}%</span>
        </div>
      )}
      <p className="text-xs font-retro text-text-muted truncate">
        {progressMessage}
        {funMsg && <span className="ml-2 text-neon-cyan retro-glow italic">{funMsg}</span>}
      </p>
    </div>
  );
}
