"use client";

import { useCallback, useRef, useState } from "react";

const TRACK_HEIGHT = 160;
const CAP_HEIGHT = 24;

export function Fader({ label, value, min, max, step, onChange, color = "#00e5ff", title }: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  color?: string;
  title?: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef<{ y: number; startValue: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const pct = (value - min) / (max - min);
  const capOffset = (1 - pct) * (TRACK_HEIGHT - CAP_HEIGHT);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStart.current = { y: e.clientY, startValue: value };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [value]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragStart.current) return;
    const dy = dragStart.current.y - e.clientY;
    const sensitivity = (max - min) / (TRACK_HEIGHT - CAP_HEIGHT);
    const newValue = dragStart.current.startValue + dy * sensitivity;
    const stepped = Math.round(newValue / step) * step;
    const clamped = Math.max(min, Math.min(max, parseFloat(stepped.toFixed(10))));
    onChange(clamped);
  }, [min, max, step, onChange]);

  const handlePointerUp = useCallback(() => {
    dragStart.current = null;
    setIsDragging(false);
  }, []);

  const displayValue = step >= 1 ? value.toFixed(0) : value.toFixed(step < 0.1 ? 2 : 1);

  return (
    <div className="flex flex-col items-center gap-1.5 select-none" style={{ minWidth: 60 }} title={title}>
      <span className="rack-section-label text-center">{label}</span>

      {/* Fader track */}
      <div
        ref={trackRef}
        className="relative cursor-grab active:cursor-grabbing"
        style={{ width: 40, height: TRACK_HEIGHT }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Track groove */}
        <div
          className="absolute left-1/2 -translate-x-1/2 rounded-sm"
          style={{
            width: 10,
            height: TRACK_HEIGHT,
            background: "linear-gradient(180deg, #0a0a12 0%, #1a1a2e 100%)",
            border: "1px inset #222",
            boxShadow: "inset 0 2px 4px rgba(0,0,0,0.8)",
          }}
        />

        {/* Fill indicator (lit portion below cap) */}
        <div
          className="absolute left-1/2 -translate-x-1/2 rounded-sm transition-all duration-75"
          style={{
            width: 8,
            bottom: 0,
            height: `${pct * 100}%`,
            background: `linear-gradient(180deg, ${color}, transparent)`,
            opacity: 0.4,
          }}
        />

        {/* Hash marks */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <div
            key={p}
            className="absolute"
            style={{
              top: (1 - p) * (TRACK_HEIGHT - CAP_HEIGHT) + CAP_HEIGHT / 2 - 0.5,
              left: 0,
              right: 0,
              height: 1,
              background: p === 0.5 ? "#555" : "#333",
            }}
          />
        ))}

        {/* Fader cap */}
        <div
          className="absolute left-0 right-0 rounded-sm transition-[top] duration-75"
          style={{
            top: capOffset,
            height: CAP_HEIGHT,
            background: isDragging
              ? `linear-gradient(180deg, #eee 0%, #999 40%, #666 100%)`
              : `linear-gradient(180deg, #ccc 0%, #888 40%, #555 100%)`,
            border: "1px outset #999",
            boxShadow: isDragging
              ? `0 0 8px ${color}60, inset 0 1px 0 rgba(255,255,255,0.4)`
              : "inset 0 1px 0 rgba(255,255,255,0.3), 0 2px 4px rgba(0,0,0,0.5)",
          }}
        >
          {/* Cap groove line */}
          <div className="absolute top-1/2 left-[3px] right-[3px] h-[1px] bg-black/30" />
        </div>
      </div>

      {/* Value readout */}
      <span className="text-base font-retro led-text tabular-nums" style={{ color }}>
        {displayValue}
      </span>
    </div>
  );
}
