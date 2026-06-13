"use client";

import { useCallback, useRef, useState, useSyncExternalStore } from "react";
import { sound, SoundSettings } from "@/lib/sound";
import { Tooltip } from "@/components/tooltip";

const SERVER_SNAPSHOT: SoundSettings = { volume: 0.5, muted: false };

const MIN_ANGLE = -135;
const MAX_ANGLE = 135;

/**
 * Faceplate audio cluster: a mini VOL knob + MUTE switch for the UI
 * sound effects. Diegetic hardware — it lives on the rack, not in a menu.
 */
export function MasterVolume() {
  const settings = useSyncExternalStore(sound.subscribe, sound.getSnapshot, () => SERVER_SNAPSHOT);
  const dragStart = useRef<{ y: number; startValue: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    dragStart.current = { y: e.clientY, startValue: sound.getSnapshot().volume };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragStart.current) return;
    const dy = dragStart.current.y - e.clientY;
    const next = Math.min(1, Math.max(0, dragStart.current.startValue + dy / 120));
    const stepped = Math.round(next * 20) / 20;
    if (stepped !== sound.getSnapshot().volume) {
      sound.setVolume(stepped);
      sound.tick();
    }
  }, []);

  const handlePointerUp = useCallback(() => {
    dragStart.current = null;
    setIsDragging(false);
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const direction = e.deltaY < 0 ? 1 : -1;
    const next = Math.min(1, Math.max(0, sound.getSnapshot().volume + direction * 0.05));
    const stepped = Math.round(next * 20) / 20;
    if (stepped !== sound.getSnapshot().volume) {
      sound.setVolume(stepped);
      sound.tick();
    }
  }, []);

  const toggleMute = useCallback(() => {
    const next = !sound.getSnapshot().muted;
    sound.setMuted(next);
    if (!next) sound.thunk();
  }, []);

  const { volume, muted } = settings;
  const angle = MIN_ANGLE + volume * (MAX_ANGLE - MIN_ANGLE);
  const effective = muted ? 0 : volume;

  return (
    <div className="flex items-center gap-2 select-none">
      <Tooltip text={"UI sound effects volume.\nDrag or scroll to adjust."}>
        <div className="flex flex-col items-center gap-0.5">
          <span
            className="font-pixel text-[7px] tracking-[0.15em]"
            style={{ color: "var(--chrome-dark)", opacity: 0.7 }}
          >
            VOL
          </span>
          <div
            className="relative w-[34px] h-[34px] cursor-grab active:cursor-grabbing"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onWheel={handleWheel}
            role="slider"
            aria-label="UI sound volume"
            aria-valuemin={0}
            aria-valuemax={1}
            aria-valuenow={volume}
            tabIndex={0}
          >
            {/* Arc indicator */}
            <svg viewBox="0 0 34 34" className="absolute inset-0 w-full h-full">
              <circle
                cx="17" cy="17" r="15"
                fill="none"
                stroke="#1a1a2e"
                strokeWidth="2"
                strokeDasharray={`${(270 / 360) * 2 * Math.PI * 15}`}
                strokeLinecap="round"
                transform="rotate(135 17 17)"
              />
              <circle
                cx="17" cy="17" r="15"
                fill="none"
                stroke={muted ? "#444" : isDragging ? "#00e5ff" : "#00b8d4"}
                strokeWidth="2"
                strokeDasharray={`${effective * (270 / 360) * 2 * Math.PI * 15} ${2 * Math.PI * 15}`}
                strokeLinecap="round"
                transform="rotate(135 17 17)"
                style={{
                  filter: muted ? "none" : "drop-shadow(0 0 2px rgba(0,229,255,0.4))",
                  transition: "stroke 0.15s",
                }}
              />
            </svg>
            {/* Knob body */}
            <div
              className="absolute inset-[5px] rounded-full overflow-hidden"
              style={{
                transform: `rotate(${angle}deg)`,
                transition: isDragging ? "none" : "transform 0.1s ease-out",
                filter: muted ? "brightness(0.55)" : "none",
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
          </div>
        </div>
      </Tooltip>

      <Tooltip text={muted ? "Unmute UI sounds" : "Mute UI sounds"}>
        <button
          onClick={toggleMute}
          className="flex flex-col items-center gap-1 cursor-pointer"
          role="switch"
          aria-checked={muted}
          aria-label="Mute UI sounds"
        >
          <span
            className="font-pixel text-[7px] tracking-[0.15em]"
            style={{ color: muted ? "var(--danger)" : "var(--chrome-dark)", opacity: muted ? 0.9 : 0.7 }}
          >
            MUTE
          </span>
          <span
            className={`pilot-light ${muted ? "pilot-light-red" : "pilot-light-off"}`}
            style={{ width: 8, height: 8 }}
          />
        </button>
      </Tooltip>
    </div>
  );
}
