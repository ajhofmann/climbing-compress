"use client";

import { useState } from "react";

export interface TunerPreset {
  name: string;
  desc: string;
}

export function PresetTuner({ presets, onSelect }: {
  presets: TunerPreset[];
  onSelect: (index: number) => void;
}) {
  const [activeIdx, setActiveIdx] = useState(0);

  const handleSelect = (idx: number) => {
    setActiveIdx(idx);
    onSelect(idx);
  };

  const needlePosition = presets.length > 1
    ? (activeIdx / (presets.length - 1)) * 100
    : 50;

  return (
    <div className="flex flex-col gap-1 w-full">
      {/* LCD preset name display */}
      <div
        className="retro-inset rounded px-3 py-1 text-center"
        style={{
          background: "#060610",
          boxShadow: "inset 0 0 8px rgba(0,0,0,0.8)",
        }}
      >
        <span className="text-sm font-pixel led-text tracking-wider">
          {presets[activeIdx]?.name ?? "---"}
        </span>
        <span className="text-sm font-retro text-text-muted ml-2">
          {presets[activeIdx]?.desc ?? ""}
        </span>
      </div>

      {/* Tuner band */}
      <div className="relative w-full">
        {/* Band background */}
        <div
          className="relative w-full h-[48px] retro-inset rounded overflow-hidden"
          style={{ background: "#080810" }}
        >
          {/* Tick marks between stations */}
          <div className="absolute inset-0 flex items-center">
            {Array.from({ length: 21 }).map((_, i) => (
              <div
                key={i}
                className="absolute top-1/2 -translate-y-1/2"
                style={{
                  left: `${(i / 20) * 100}%`,
                  width: 1,
                  height: i % 5 === 0 ? 12 : 6,
                  background: i % 5 === 0 ? "#333" : "#222",
                }}
              />
            ))}
          </div>

          {/* Station labels */}
          <div className="absolute inset-0 flex items-center">
            {presets.map((p, i) => {
              const pos = presets.length > 1 ? (i / (presets.length - 1)) * 100 : 50;
              const isActive = i === activeIdx;
              return (
                <button
                  key={p.name}
                  onClick={() => handleSelect(i)}
                  className="absolute -translate-x-1/2 text-sm font-pixel uppercase tracking-wider cursor-pointer transition-all z-10 px-1"
                  style={{
                    left: `${pos}%`,
                    color: isActive ? "var(--neon-cyan)" : "var(--text-muted)",
                    textShadow: isActive ? "0 0 6px rgba(0,229,255,0.5)" : "none",
                    top: "50%",
                    transform: "translate(-50%, -50%)",
                  }}
                  title={p.desc}
                >
                  {p.name}
                </button>
              );
            })}
          </div>

          {/* Sliding needle indicator */}
          <div
            className="absolute top-0 bottom-0 w-[2px] z-20 transition-all duration-300"
            style={{
              left: `${needlePosition}%`,
              transform: "translateX(-50%)",
              background: "var(--neon-cyan)",
              boxShadow: "0 0 6px var(--neon-cyan), 0 0 12px rgba(0,229,255,0.3)",
              transitionTimingFunction: "cubic-bezier(0.34, 1.56, 0.64, 1)", // spring
            }}
          />

          {/* Needle glow halo */}
          <div
            className="absolute top-0 bottom-0 w-[20px] z-[15] transition-all duration-300 pointer-events-none"
            style={{
              left: `${needlePosition}%`,
              transform: "translateX(-50%)",
              background: "radial-gradient(ellipse at center, rgba(0,229,255,0.1) 0%, transparent 70%)",
              transitionTimingFunction: "cubic-bezier(0.34, 1.56, 0.64, 1)",
            }}
          />
        </div>
      </div>
    </div>
  );
}
