"use client";

import { useEffect } from "react";
import { sound } from "@/lib/sound";

/**
 * Global button-sound delegation. Any `.vcr-btn` or `.retro-btn` press
 * plays the soft hardware click without per-component wiring.
 * Components with bespoke sounds (toggles, knobs) call the engine directly.
 */
export function SoundFx() {
  useEffect(() => {
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const btn = target.closest(".vcr-btn, .retro-btn");
      if (!btn || (btn as HTMLButtonElement).disabled) return;
      sound.click();
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => document.removeEventListener("pointerdown", onPointerDown, true);
  }, []);

  return null;
}
