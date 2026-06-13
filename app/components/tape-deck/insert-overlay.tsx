"use client";

import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";

interface TapeAnim {
  mode: "insert" | "eject";
  name: string;
  key: number;
}

/**
 * INSERT TAPE / EJECT overlay — when a clip loads (upload, library pick,
 * swap) a cassette slides up into the deck slit; on eject it slides back
 * out. Triggered by watching videoId transitions in the store.
 */
export function TapeInsertOverlay() {
  const videoId = useStore((s) => s.videoId);
  const videoName = useStore((s) => s.videoName);
  const [anim, setAnim] = useState<TapeAnim | null>(null);
  const [prev, setPrev] = useState<{ id: string | null; name: string | null }>({ id: videoId, name: videoName });

  // Render-time adjustment: detect clip transitions without effect-driven setState.
  if (prev.id !== videoId) {
    const prevName = prev.name;
    setPrev({ id: videoId, name: videoName });
    if (videoId) {
      setAnim((a) => ({ mode: "insert", name: videoName ?? "untitled tape", key: (a?.key ?? 0) + 1 }));
    } else if (prev.id) {
      setAnim((a) => ({ mode: "eject", name: prevName ?? "", key: (a?.key ?? 0) + 1 }));
    }
  } else if (prev.name !== videoName) {
    setPrev({ id: videoId, name: videoName });
  }

  // Auto-dismiss once the animation has played out.
  useEffect(() => {
    if (!anim) return;
    const timer = window.setTimeout(() => setAnim(null), 2050);
    return () => window.clearTimeout(timer);
  }, [anim]);

  if (!anim) return null;

  return (
    <div className="tape-overlay" key={anim.key} aria-hidden="true">
      {/* Deck faceplate with tape slit — cassette vanishes behind it */}
      <div className="tape-deck-face">
        <div className="tape-deck-slit" />
      </div>

      {/* The cassette */}
      <div className={`tape-cassette ${anim.mode === "insert" ? "tape-cassette--insert" : "tape-cassette--eject"}`}>
        <div className="relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/retro/vhs-tape-label.png"
            alt=""
            className="w-full h-auto"
            draggable={false}
          />
          {anim.name && (
            <span className="tape-cassette-name">{anim.name}</span>
          )}
        </div>
      </div>

      <span className="tape-overlay-status">
        {anim.mode === "insert" ? "INSERTING TAPE" : "EJECTING TAPE"}
      </span>
    </div>
  );
}
