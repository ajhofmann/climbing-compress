"use client";

import { Tooltip } from "@/components/tooltip";
import { sound } from "@/lib/sound";

const MIN_ANGLE = -135;
const MAX_ANGLE = 135;

export function RotarySelect<T extends string | number>({ label, value, options, onChange, title }: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  title?: string;
}) {
  const currentIdx = options.findIndex(o => o.value === value);
  const pct = options.length > 1 ? currentIdx / (options.length - 1) : 0.5;
  const angle = MIN_ANGLE + pct * (MAX_ANGLE - MIN_ANGLE);

  const handleClick = () => {
    const nextIdx = (currentIdx + 1) % options.length;
    sound.tick();
    onChange(options[nextIdx].value);
  };

  const content = (
    <div className="flex flex-col items-center gap-1.5 select-none" style={{ minWidth: 110 }}>
      <span className="rack-section-label">{label}</span>

      {/* Knob + position labels */}
      <div className="relative w-[90px] h-[90px]">
        {/* Position labels around the arc */}
        {options.map((opt, i) => {
          const optPct = options.length > 1 ? i / (options.length - 1) : 0.5;
          const optAngle = MIN_ANGLE + optPct * (MAX_ANGLE - MIN_ANGLE);
          const rad = (optAngle * Math.PI) / 180;
          const r = 50;
          const x = 45 + r * Math.sin(rad);
          const y = 45 - r * Math.cos(rad);
          const isActive = i === currentIdx;
          return (
            <span
              key={String(opt.value)}
              className="absolute text-sm font-pixel uppercase -translate-x-1/2 -translate-y-1/2"
              style={{
                left: x,
                top: y,
                color: isActive ? "var(--neon-cyan)" : "var(--text-muted)",
                textShadow: isActive ? "0 0 4px rgba(0,229,255,0.5)" : "none",
              }}
            >
              {opt.label}
            </span>
          );
        })}

        {/* Detent dots */}
        <svg viewBox="0 0 90 90" className="absolute inset-0 w-full h-full">
          {options.map((_, i) => {
            const optPct = options.length > 1 ? i / (options.length - 1) : 0.5;
            const optAngle = MIN_ANGLE + optPct * (MAX_ANGLE - MIN_ANGLE);
            const rad = (optAngle * Math.PI) / 180;
            const r = 38;
            return (
              <circle
                key={i}
                cx={45 + r * Math.sin(rad)}
                cy={45 - r * Math.cos(rad)}
                r={i === currentIdx ? 2 : 1.2}
                fill={i === currentIdx ? "#00e5ff" : "#444"}
              />
            );
          })}
        </svg>

        {/* Knob body (click to cycle) */}
        <div
          className="absolute inset-[18px] rounded-full cursor-pointer"
          onClick={handleClick}
          style={{
            transform: `rotate(${angle}deg)`,
            transition: "transform 0.15s ease-out",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/retro/knob.png"
            alt=""
            className="w-full h-full object-cover rounded-full pointer-events-none"
            draggable={false}
          />
        </div>
      </div>

      {/* Current value readout */}
      <span className="text-base font-retro led-text">
        {options[currentIdx]?.label ?? "?"}
      </span>
    </div>
  );

  return title ? <Tooltip text={title}>{content}</Tooltip> : content;
}
