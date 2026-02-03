"use client";

import { useCallback, useRef, useState } from "react";

interface BodyMapProps {
  handWeight: number;
  footWeight: number;
  coreWeight: number;
  onHandChange: (v: number) => void;
  onFootChange: (v: number) => void;
  onCoreChange: (v: number) => void;
}

const COLORS = {
  hand: "#00e5ff",
  foot: "#e040fb",
  core: "#ff6e40",
};

type Zone = "hand" | "foot" | "core";

function zoneMax(zone: Zone): number {
  return zone === "core" ? 20 : 10;
}

export function BodyMap({ handWeight, footWeight, coreWeight, onHandChange, onFootChange, onCoreChange }: BodyMapProps) {
  const [activeZone, setActiveZone] = useState<Zone | null>(null);
  const [hoverZone, setHoverZone] = useState<Zone | null>(null);
  const dragStart = useRef<{ y: number; startValue: number; zone: Zone } | null>(null);

  const getWeight = (z: Zone) => z === "hand" ? handWeight : z === "foot" ? footWeight : coreWeight;
  const getOnChange = (z: Zone) => z === "hand" ? onHandChange : z === "foot" ? onFootChange : onCoreChange;

  const handlePointerDown = useCallback((e: React.PointerEvent, zone: Zone) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setActiveZone(zone);
    dragStart.current = { y: e.clientY, startValue: getWeight(zone), zone };
  }, [handWeight, footWeight, coreWeight]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragStart.current) return;
    const { zone, y, startValue } = dragStart.current;
    const dy = y - e.clientY;
    const max = zoneMax(zone);
    const sensitivity = max / 80;
    const newValue = Math.max(0, Math.min(max, startValue + dy * sensitivity));
    const stepped = Math.round(newValue * 10) / 10;
    getOnChange(zone)(stepped);
  }, [onHandChange, onFootChange, onCoreChange]);

  const handlePointerUp = useCallback(() => {
    dragStart.current = null;
    setActiveZone(null);
  }, []);

  const glowIntensity = (zone: Zone) => {
    const w = getWeight(zone);
    const max = zoneMax(zone);
    return 0.15 + (w / max) * 0.85;
  };

  const zoneColor = (zone: Zone) => COLORS[zone];
  const isActive = (zone: Zone) => activeZone === zone;
  const isHover = (zone: Zone) => hoverZone === zone;

  const glowFilter = (zone: Zone) => {
    const intensity = glowIntensity(zone);
    const color = zoneColor(zone);
    if (isActive(zone)) return `drop-shadow(0 0 8px ${color}) drop-shadow(0 0 16px ${color})`;
    if (isHover(zone)) return `drop-shadow(0 0 6px ${color})`;
    return `drop-shadow(0 0 ${3 * intensity}px ${color})`;
  };

  return (
    <div className="flex flex-col items-center gap-1 select-none">
      <span className="rack-section-label">WEIGHTS</span>
      <div
        className="relative"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <svg width="110" height="170" viewBox="0 0 110 170">
          {/* Body structure (dim lines) */}
          {/* Head */}
          <circle cx="55" cy="18" r="11" fill="none" stroke="#333" strokeWidth="2" />
          {/* Spine */}
          <line x1="55" y1="29" x2="55" y2="95" stroke="#333" strokeWidth="2" />
          {/* Arms */}
          <line x1="55" y1="40" x2="16" y2="73" stroke="#333" strokeWidth="2" />
          <line x1="55" y1="40" x2="94" y2="73" stroke="#333" strokeWidth="2" />
          {/* Legs */}
          <line x1="55" y1="95" x2="28" y2="140" stroke="#333" strokeWidth="2" />
          <line x1="55" y1="95" x2="82" y2="140" stroke="#333" strokeWidth="2" />

          {/* HAND zones (wrists/forearms) */}
          <g
            className="cursor-grab active:cursor-grabbing"
            onPointerDown={(e) => handlePointerDown(e, "hand")}
            onPointerEnter={() => setHoverZone("hand")}
            onPointerLeave={() => setHoverZone(null)}
            style={{ filter: glowFilter("hand") }}
          >
            {/* Left hand */}
            <circle cx="16" cy="73" r="8" fill={COLORS.hand} opacity={glowIntensity("hand")} />
            <circle cx="16" cy="73" r="4" fill="#fff" opacity={glowIntensity("hand") * 0.5} />
            {/* Right hand */}
            <circle cx="94" cy="73" r="8" fill={COLORS.hand} opacity={glowIntensity("hand")} />
            <circle cx="94" cy="73" r="4" fill="#fff" opacity={glowIntensity("hand") * 0.5} />
            {/* Invisible larger hit area */}
            <circle cx="16" cy="73" r="16" fill="transparent" />
            <circle cx="94" cy="73" r="16" fill="transparent" />
          </g>

          {/* CORE zone (torso center) */}
          <g
            className="cursor-grab active:cursor-grabbing"
            onPointerDown={(e) => handlePointerDown(e, "core")}
            onPointerEnter={() => setHoverZone("core")}
            onPointerLeave={() => setHoverZone(null)}
            style={{ filter: glowFilter("core") }}
          >
            <ellipse cx="55" cy="64" rx="14" ry="22" fill={COLORS.core} opacity={glowIntensity("core") * 0.5} />
            <ellipse cx="55" cy="64" rx="7" ry="14" fill="#fff" opacity={glowIntensity("core") * 0.2} />
            {/* Larger hit area */}
            <ellipse cx="55" cy="64" rx="22" ry="30" fill="transparent" />
          </g>

          {/* FOOT zones (ankles) */}
          <g
            className="cursor-grab active:cursor-grabbing"
            onPointerDown={(e) => handlePointerDown(e, "foot")}
            onPointerEnter={() => setHoverZone("foot")}
            onPointerLeave={() => setHoverZone(null)}
            style={{ filter: glowFilter("foot") }}
          >
            {/* Left foot */}
            <circle cx="28" cy="140" r="8" fill={COLORS.foot} opacity={glowIntensity("foot")} />
            <circle cx="28" cy="140" r="4" fill="#fff" opacity={glowIntensity("foot") * 0.5} />
            {/* Right foot */}
            <circle cx="82" cy="140" r="8" fill={COLORS.foot} opacity={glowIntensity("foot")} />
            <circle cx="82" cy="140" r="4" fill="#fff" opacity={glowIntensity("foot") * 0.5} />
            <circle cx="28" cy="140" r="16" fill="transparent" />
            <circle cx="82" cy="140" r="16" fill="transparent" />
          </g>
        </svg>
      </div>

      {/* Value readouts */}
      <div className="flex gap-3 text-sm font-retro">
        <span style={{ color: COLORS.hand, textShadow: `0 0 4px ${COLORS.hand}60` }}>H:{handWeight.toFixed(1)}</span>
        <span style={{ color: COLORS.core, textShadow: `0 0 4px ${COLORS.core}60` }}>C:{coreWeight.toFixed(1)}</span>
        <span style={{ color: COLORS.foot, textShadow: `0 0 4px ${COLORS.foot}60` }}>F:{footWeight.toFixed(1)}</span>
      </div>
    </div>
  );
}
