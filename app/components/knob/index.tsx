"use client";

import { useCallback, useRef, useState } from "react";

const MIN_ANGLE = -135; // 7 o'clock position
const MAX_ANGLE = 135;  // 5 o'clock position
const ANGLE_RANGE = MAX_ANGLE - MIN_ANGLE; // 270 degrees

function valueToAngle(value: number, min: number, max: number): number {
  const pct = (value - min) / (max - min);
  return MIN_ANGLE + pct * ANGLE_RANGE;
}

// Generate tick marks around the arc
function Ticks({ count, value, min, max }: { count: number; value: number; min: number; max: number }) {
  const ticks = [];
  const valuePct = (value - min) / (max - min);
  for (let i = 0; i <= count; i++) {
    const pct = i / count;
    const angle = MIN_ANGLE + pct * ANGLE_RANGE;
    const rad = (angle * Math.PI) / 180;
    const r1 = 38;
    const isMajor = i % (count / 2) === 0;
    const r2 = isMajor ? 44 : 42;
    const isLit = pct <= valuePct;
    ticks.push(
      <line
        key={i}
        x1={50 + r1 * Math.sin(rad)}
        y1={50 - r1 * Math.cos(rad)}
        x2={50 + r2 * Math.sin(rad)}
        y2={50 - r2 * Math.cos(rad)}
        stroke={isLit ? "#00e5ff" : isMajor ? "#555" : "#333"}
        strokeWidth={isMajor ? 1.5 : 0.8}
        strokeLinecap="round"
        style={isLit ? { filter: "drop-shadow(0 0 2px rgba(0,229,255,0.6))" } : undefined}
      />
    );
  }
  return <>{ticks}</>;
}

export function Knob({ label, info, value, min, max, step, onChange }: {
  label: string;
  info?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  const knobRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef<{ y: number; startValue: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const angle = valueToAngle(value, min, max);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStart.current = { y: e.clientY, startValue: value };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [value]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragStart.current) return;
    const dy = dragStart.current.y - e.clientY;
    const sensitivity = (max - min) / 150;
    const newValue = dragStart.current.startValue + dy * sensitivity;
    const stepped = Math.round(newValue / step) * step;
    const clamped = Math.max(min, Math.min(max, parseFloat(stepped.toFixed(10))));
    onChange(clamped);
  }, [min, max, step, onChange]);

  const handlePointerUp = useCallback(() => {
    dragStart.current = null;
    setIsDragging(false);
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const direction = e.deltaY < 0 ? 1 : -1;
    const newValue = value + direction * step;
    const clamped = Math.max(min, Math.min(max, parseFloat(newValue.toFixed(10))));
    onChange(clamped);
  }, [value, min, max, step, onChange]);

  const displayValue = step >= 1 ? value.toFixed(0) : value.toFixed(step < 0.1 ? 2 : 1);
  const pct = (value - min) / (max - min);

  return (
    <div className="flex flex-col items-center gap-1.5 select-none" style={{ minWidth: 130 }}>
      {/* Label */}
      <span className="text-base font-pixel text-text-muted uppercase tracking-wider text-center leading-tight">
        {label}
      </span>

      {/* Knob container */}
      <div
        ref={knobRef}
        className="relative w-[110px] h-[110px] cursor-grab active:cursor-grabbing"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
        title={info}
      >
        {/* SVG tick marks + glow ring */}
        <svg
          viewBox="0 0 100 100"
          className="absolute inset-0 w-full h-full"
          style={{
            filter: isDragging ? "drop-shadow(0 0 8px rgba(0,229,255,0.5))" : "none",
            transition: "filter 0.15s",
          }}
        >
          {/* Outer glow ring on drag */}
          {isDragging && (
            <circle
              cx="50" cy="50" r="46"
              fill="none"
              stroke="rgba(0,229,255,0.15)"
              strokeWidth="1"
            />
          )}

          {/* Background arc (track) */}
          <circle
            cx="50" cy="50" r="36"
            fill="none"
            stroke="#1a1a2e"
            strokeWidth="4"
            strokeDasharray={`${(270 / 360) * 2 * Math.PI * 36}`}
            strokeDashoffset={`${((360 - 270) / 360) * 2 * Math.PI * 36 / 2}`}
            strokeLinecap="round"
            transform="rotate(135 50 50)"
          />
          {/* Active arc (filled portion) — wider and glowier */}
          <circle
            cx="50" cy="50" r="36"
            fill="none"
            stroke={isDragging ? "#00e5ff" : "#00b8d4"}
            strokeWidth="4"
            strokeDasharray={`${pct * (270 / 360) * 2 * Math.PI * 36} ${2 * Math.PI * 36}`}
            strokeLinecap="round"
            transform="rotate(135 50 50)"
            style={{
              filter: isDragging
                ? "drop-shadow(0 0 6px rgba(0,229,255,0.8))"
                : "drop-shadow(0 0 2px rgba(0,229,255,0.3))",
              transition: "stroke 0.15s, filter 0.15s",
            }}
          />

          {/* Indicator needle at current angle */}
          {(() => {
            const rad = (angle * Math.PI) / 180;
            const r1 = 20, r2 = 34;
            return (
              <line
                x1={50 + r1 * Math.sin(rad)}
                y1={50 - r1 * Math.cos(rad)}
                x2={50 + r2 * Math.sin(rad)}
                y2={50 - r2 * Math.cos(rad)}
                stroke={isDragging ? "#fff" : "#ccc"}
                strokeWidth="2"
                strokeLinecap="round"
                style={{
                  filter: isDragging ? "drop-shadow(0 0 3px rgba(0,229,255,0.8))" : "none",
                }}
              />
            );
          })()}

          <Ticks count={10} value={value} min={min} max={max} />
        </svg>

        {/* Knob body (rotated) */}
        <div
          className="absolute inset-[16px] rounded-full overflow-hidden"
          style={{
            transform: `rotate(${angle}deg)`,
            transition: isDragging ? "none" : "transform 0.1s ease-out",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/retro/knob.png"
            alt=""
            className="w-full h-full object-cover pointer-events-none"
            draggable={false}
          />
        </div>

        {/* Center dot — glows when dragging */}
        <div
          className="absolute rounded-full"
          style={{
            width: 6, height: 6,
            top: "50%", left: "50%",
            transform: "translate(-50%, -50%)",
            background: isDragging ? "#00e5ff" : "#666",
            boxShadow: isDragging ? "0 0 4px #00e5ff, 0 0 8px rgba(0,229,255,0.4)" : "none",
            transition: "all 0.15s",
          }}
        />
      </div>

      {/* Value readout — LED display */}
      <div
        className="px-2 py-0.5 rounded-sm"
        style={{
          background: "#0a0a14",
          border: "1px inset #222",
          boxShadow: "inset 0 1px 3px rgba(0,0,0,0.5)",
        }}
      >
        <span
          className="text-lg font-retro tabular-nums"
          style={{
            color: isDragging ? "#00e5ff" : "#00b8d4",
            textShadow: isDragging
              ? "0 0 6px rgba(0,229,255,0.6), 0 0 12px rgba(0,229,255,0.3)"
              : "0 0 4px rgba(0,229,255,0.3)",
            letterSpacing: "0.05em",
          }}
        >
          {displayValue}
        </span>
      </div>

      {/* Info text */}
      {info && (
        <span className="text-xs text-text-muted text-center leading-tight max-w-[120px]">
          {info}
        </span>
      )}
    </div>
  );
}
