"use client";

import { useCallback, useRef, useState } from "react";
import { Tooltip } from "@/components/tooltip";
import { sound } from "@/lib/sound";

const MIN_ANGLE = -135;
const MAX_ANGLE = 135;

// "" = ungraded, then VB, V0..V12. Index 0 is ungraded.
export const GRADE_OPTIONS = ["", "VB", "V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12"] as const;

function gradeIndex(grade: string): number {
  const i = GRADE_OPTIONS.indexOf(grade as (typeof GRADE_OPTIONS)[number]);
  return i < 0 ? 0 : i;
}

/**
 * Rotary grade dial — drag up/down (or scroll) to set the climb's V-grade.
 * The grade is metadata that tags the clip and prints on the SENT! card.
 */
export function GradeDial({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const dragStart = useRef<{ y: number; startIdx: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const idx = gradeIndex(value);
  const maxIdx = GRADE_OPTIONS.length - 1;
  const pct = idx / maxIdx;
  const angle = MIN_ANGLE + pct * (MAX_ANGLE - MIN_ANGLE);
  const label = GRADE_OPTIONS[idx] || "—";

  const setIdx = useCallback((nextIdx: number) => {
    const clamped = Math.max(0, Math.min(maxIdx, nextIdx));
    if (clamped !== gradeIndex(value)) {
      sound.tick();
      onChange(GRADE_OPTIONS[clamped]);
    }
  }, [maxIdx, value, onChange]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStart.current = { y: e.clientY, startIdx: gradeIndex(value) };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [value]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragStart.current) return;
    const dy = dragStart.current.y - e.clientY;
    setIdx(dragStart.current.startIdx + Math.round(dy / 14));
  }, [setIdx]);

  const handlePointerUp = useCallback(() => {
    dragStart.current = null;
    setIsDragging(false);
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setIdx(gradeIndex(value) + (e.deltaY < 0 ? 1 : -1));
  }, [setIdx, value]);

  return (
    <Tooltip text={"Climb grade (V-scale).\nDrag or scroll to set. Prints on the SENT! card.\nLeftmost = ungraded."}>
      <div className="flex flex-col items-center gap-1.5 select-none" style={{ minWidth: 90 }}>
        <span className="rack-section-label">GRADE</span>
        <div
          className="relative w-[72px] h-[72px] cursor-grab active:cursor-grabbing"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onWheel={handleWheel}
          role="slider"
          aria-label="Climb grade"
          aria-valuemin={0}
          aria-valuemax={maxIdx}
          aria-valuenow={idx}
          aria-valuetext={label}
          tabIndex={0}
        >
          <svg viewBox="0 0 72 72" className="absolute inset-0 w-full h-full"
            style={{ filter: isDragging ? "drop-shadow(0 0 6px rgba(224,64,251,0.5))" : "none" }}>
            <circle cx="36" cy="36" r="28" fill="none" stroke="#1a1a2e" strokeWidth="3"
              strokeDasharray={`${(270 / 360) * 2 * Math.PI * 28}`}
              strokeLinecap="round" transform="rotate(135 36 36)" />
            <circle cx="36" cy="36" r="28" fill="none"
              stroke={isDragging ? "#e040fb" : "#b030c0"} strokeWidth="3"
              strokeDasharray={`${pct * (270 / 360) * 2 * Math.PI * 28} ${2 * Math.PI * 28}`}
              strokeLinecap="round" transform="rotate(135 36 36)"
              style={{ filter: "drop-shadow(0 0 3px rgba(224,64,251,0.4))", transition: "stroke 0.15s" }} />
          </svg>
          <div className="absolute inset-[12px] rounded-full overflow-hidden"
            style={{ transform: `rotate(${angle}deg)`, transition: isDragging ? "none" : "transform 0.1s ease-out" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/retro/knob.png" alt="" className="w-full h-full object-cover pointer-events-none" draggable={false} />
          </div>
        </div>
        <div className="px-2 py-0.5 rounded-sm" style={{ background: "#0a0a14", border: "1px inset #222", minWidth: 44, textAlign: "center" }}>
          <span className="text-lg font-retro tabular-nums" style={{
            color: idx === 0 ? "var(--text-muted)" : "var(--neon-magenta)",
            textShadow: idx === 0 ? "none" : "0 0 6px rgba(224,64,251,0.5)",
            letterSpacing: "0.05em",
          }}>
            {label}
          </span>
        </div>
      </div>
    </Tooltip>
  );
}
