"use client";

import { useCallback } from "react";
import { Tooltip } from "@/components/tooltip";

// 7-segment digit paths for SVG rendering -- now styled as Nixie tubes
const SEGMENTS: Record<string, boolean[]> = {
  // [top, topRight, bottomRight, bottom, bottomLeft, topLeft, middle]
  "0": [true,  true,  true,  true,  true,  true,  false],
  "1": [false, true,  true,  false, false, false, false],
  "2": [true,  true,  false, true,  true,  false, true],
  "3": [true,  true,  true,  true,  false, false, true],
  "4": [false, true,  true,  false, false, true,  true],
  "5": [true,  false, true,  true,  false, true,  true],
  "6": [true,  false, true,  true,  true,  true,  true],
  "7": [true,  true,  true,  false, false, false, false],
  "8": [true,  true,  true,  true,  true,  true,  true],
  "9": [true,  true,  true,  true,  false, true,  true],
  ":": [],
};

const NIXIE_ON = "#ffaa44";
const NIXIE_GHOST = "rgba(255,170,68,0.07)";
const NIXIE_GLOW = "rgba(255,170,68,0.6)";

function NixieDigit({ char }: { char: string }) {
  if (char === ":") {
    return (
      <div className="flex flex-col items-center justify-center gap-3 px-1" style={{ height: 60 }}>
        <div className="w-[3px] h-[3px] rounded-full" style={{ background: NIXIE_ON, boxShadow: `0 0 4px ${NIXIE_GLOW}` }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ background: NIXIE_ON, boxShadow: `0 0 4px ${NIXIE_GLOW}` }} />
      </div>
    );
  }

  const segs = SEGMENTS[char] || SEGMENTS["0"];

  return (
    <div className="relative nixie-tube">
      {/* Glass tube envelope */}
      <div
        className="relative rounded-md overflow-hidden"
        style={{
          width: 36,
          height: 60,
          background: "linear-gradient(180deg, rgba(40,25,10,0.6) 0%, rgba(20,12,5,0.8) 100%)",
          border: "1px solid rgba(255,170,68,0.12)",
          boxShadow: "inset 0 1px 0 rgba(255,200,100,0.08), inset 0 -1px 0 rgba(0,0,0,0.3)",
        }}
      >
        {/* Glass highlight */}
        <div
          className="absolute inset-x-1 top-0 h-[6px] rounded-b-full"
          style={{
            background: "linear-gradient(180deg, rgba(255,200,150,0.1) 0%, transparent 100%)",
          }}
        />

        {/* Digit SVG */}
        <svg width="36" height="60" viewBox="0 0 36 60" className="relative z-10">
          {/* Ghost "8" (all segments very faint) */}
          <rect x="8" y="4" width="20" height="4" rx="1.5" fill={NIXIE_GHOST} />
          <rect x="27" y="8" width="4" height="18" rx="1.5" fill={NIXIE_GHOST} />
          <rect x="27" y="30" width="4" height="18" rx="1.5" fill={NIXIE_GHOST} />
          <rect x="8" y="52" width="20" height="4" rx="1.5" fill={NIXIE_GHOST} />
          <rect x="5" y="30" width="4" height="18" rx="1.5" fill={NIXIE_GHOST} />
          <rect x="5" y="8" width="4" height="18" rx="1.5" fill={NIXIE_GHOST} />
          <rect x="8" y="27" width="20" height="4" rx="1.5" fill={NIXIE_GHOST} />

          {/* Active segments */}
          {segs[0] && <rect x="8" y="4" width="20" height="4" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
          {segs[1] && <rect x="27" y="8" width="4" height="18" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
          {segs[2] && <rect x="27" y="30" width="4" height="18" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
          {segs[3] && <rect x="8" y="52" width="20" height="4" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
          {segs[4] && <rect x="5" y="30" width="4" height="18" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
          {segs[5] && <rect x="5" y="8" width="4" height="18" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
          {segs[6] && <rect x="8" y="27" width="20" height="4" rx="1.5" fill={NIXIE_ON} style={{ filter: `drop-shadow(0 0 4px ${NIXIE_GLOW})` }} />}
        </svg>
      </div>
    </div>
  );
}

export function LedCounter({ label, value, min, max, step, onChange, title }: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  title?: string;
}) {
  const increment = useCallback(() => {
    const next = Math.min(max, value + step);
    onChange(parseFloat(next.toFixed(10)));
  }, [value, max, step, onChange]);

  const decrement = useCallback(() => {
    const next = Math.max(min, value - step);
    onChange(parseFloat(next.toFixed(10)));
  }, [value, min, step, onChange]);

  // Format as MM:SS if duration-like (> 59), else just seconds
  const isTime = max > 59;
  let displayChars: string[];
  if (isTime) {
    const mins = Math.floor(value / 60);
    const secs = Math.round(value % 60);
    displayChars = [
      ...String(mins).padStart(2, "0").split(""),
      ":",
      ...String(secs).padStart(2, "0").split(""),
    ];
  } else {
    displayChars = String(Math.round(value)).padStart(3, " ").split("").map(c => c === " " ? "0" : c);
  }

  const content = (
    <div className="flex flex-col items-center gap-1.5">
      <span className="rack-section-label">{label}</span>
      <div className="flex items-center gap-1.5">
        <button
          onClick={decrement}
          className="retro-btn w-10 h-14 flex items-center justify-center font-retro leading-none"
          style={{ fontSize: "24px", padding: 0, color: NIXIE_ON }}
        >
          -
        </button>

        {/* Nixie tube display housing */}
        <div
          className="retro-inset rounded px-1.5 py-1 flex items-center gap-[2px]"
          style={{
            background: "#0c0804",
            boxShadow: `inset 0 0 12px rgba(0,0,0,0.9), 0 0 6px rgba(255,170,68,0.05)`,
          }}
        >
          {displayChars.map((c, i) => (
            <NixieDigit key={i} char={c} />
          ))}
        </div>

        <button
          onClick={increment}
          className="retro-btn w-10 h-14 flex items-center justify-center font-retro leading-none"
          style={{ fontSize: "24px", padding: 0, color: NIXIE_ON }}
        >
          +
        </button>
      </div>
    </div>
  );

  return title ? <Tooltip text={title}>{content}</Tooltip> : content;
}
