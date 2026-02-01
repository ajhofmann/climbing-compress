"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { CropBox, AspectPreset } from "@/lib/types";

const PRESETS: { label: string; value: AspectPreset; ratio: number | null }[] = [
  { label: "None", value: null, ratio: null },
  { label: "9:16", value: "9:16", ratio: 9 / 16 },
  { label: "4:5", value: "4:5", ratio: 4 / 5 },
  { label: "1:1", value: "1:1", ratio: 1 },
  { label: "16:9", value: "16:9", ratio: 16 / 9 },
];

function computeCrop(targetAR: number, srcAR: number): CropBox {
  const r = targetAR / srcAR;
  if (r <= 1) {
    const w = r;
    return { x: (1 - w) / 2, y: 0, w, h: 1 };
  }
  const h = 1 / r;
  return { x: 0, y: (1 - h) / 2, w: 1, h };
}

function clampCrop(crop: CropBox): CropBox {
  const w = Math.min(crop.w, 1);
  const h = Math.min(crop.h, 1);
  const x = Math.max(0, Math.min(crop.x, 1 - w));
  const y = Math.max(0, Math.min(crop.y, 1 - h));
  return { x, y, w, h };
}

export function CropEditor() {
  const { videoInfo, thumbnails, crop, setCrop } = useStore();
  const [preset, setPreset] = useState<AspectPreset>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    mode: "move" | "nw" | "ne" | "sw" | "se";
    startX: number;
    startY: number;
    startCrop: CropBox;
  } | null>(null);

  const srcAR = videoInfo ? videoInfo.width / videoInfo.height : 16 / 9;
  const thumb = thumbnails.length > 0 ? thumbnails[Math.floor(thumbnails.length / 2)] : null;

  const selectPreset = useCallback(
    (p: AspectPreset, ratio: number | null) => {
      setPreset(p);
      if (!p || !ratio) {
        setCrop(null);
        return;
      }
      setCrop(clampCrop(computeCrop(ratio, srcAR)));
    },
    [srcAR, setCrop],
  );

  // Convert pixel coords on container to normalized 0-1 coords
  const pxToNorm = useCallback(
    (clientX: number, clientY: number): { nx: number; ny: number } => {
      const el = containerRef.current;
      if (!el) return { nx: 0, ny: 0 };
      const rect = el.getBoundingClientRect();
      return {
        nx: (clientX - rect.left) / rect.width,
        ny: (clientY - rect.top) / rect.height,
      };
    },
    [],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent, mode: "move" | "nw" | "ne" | "sw" | "se") => {
      if (!crop) return;
      e.preventDefault();
      e.stopPropagation();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      dragRef.current = {
        mode,
        startX: e.clientX,
        startY: e.clientY,
        startCrop: { ...crop },
      };
    },
    [crop],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const drag = dragRef.current;
      if (!drag || !crop) return;

      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const dx = (e.clientX - drag.startX) / rect.width;
      const dy = (e.clientY - drag.startY) / rect.height;
      const sc = drag.startCrop;

      if (drag.mode === "move") {
        setCrop(
          clampCrop({
            x: sc.x + dx,
            y: sc.y + dy,
            w: sc.w,
            h: sc.h,
          }),
        );
        return;
      }

      // Corner resize — maintain aspect ratio
      const currentPreset = PRESETS.find((p) => p.value === preset);
      const targetAR = currentPreset?.ratio;

      let newCrop: CropBox;

      if (drag.mode === "se") {
        let nw = Math.max(0.1, sc.w + dx);
        let nh = targetAR ? nw * srcAR / targetAR : Math.max(0.1, sc.h + dy);
        nw = targetAR ? nh * targetAR / srcAR : nw;
        newCrop = { x: sc.x, y: sc.y, w: nw, h: nh };
      } else if (drag.mode === "nw") {
        let nw = Math.max(0.1, sc.w - dx);
        let nh = targetAR ? nw * srcAR / targetAR : Math.max(0.1, sc.h - dy);
        nw = targetAR ? nh * targetAR / srcAR : nw;
        newCrop = {
          x: sc.x + sc.w - nw,
          y: sc.y + sc.h - nh,
          w: nw,
          h: nh,
        };
      } else if (drag.mode === "ne") {
        let nw = Math.max(0.1, sc.w + dx);
        let nh = targetAR ? nw * srcAR / targetAR : Math.max(0.1, sc.h - dy);
        nw = targetAR ? nh * targetAR / srcAR : nw;
        newCrop = {
          x: sc.x,
          y: sc.y + sc.h - nh,
          w: nw,
          h: nh,
        };
      } else {
        // sw
        let nw = Math.max(0.1, sc.w - dx);
        let nh = targetAR ? nw * srcAR / targetAR : Math.max(0.1, sc.h + dy);
        nw = targetAR ? nh * targetAR / srcAR : nw;
        newCrop = {
          x: sc.x + sc.w - nw,
          y: sc.y,
          w: nw,
          h: nh,
        };
      }

      setCrop(clampCrop(newCrop));
    },
    [crop, preset, srcAR, setCrop],
  );

  const handlePointerUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  if (!thumb || !videoInfo) return null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-semibold text-text-muted mr-1">Crop</span>
        {PRESETS.map((p) => (
          <button
            key={p.label}
            onClick={() => selectPreset(p.value, p.ratio)}
            className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
              preset === p.value
                ? p.value === null
                  ? "bg-bg-input text-text border border-border"
                  : "bg-accent text-white shadow-sm"
                : "bg-bg-card text-text-muted border border-border hover:border-accent-light hover:text-text"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div
        ref={containerRef}
        className="relative rounded-xl overflow-hidden select-none"
        style={{ aspectRatio: `${videoInfo.width} / ${videoInfo.height}` }}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Background frame */}
        <img
          src={thumb}
          alt="crop preview"
          draggable={false}
          className="absolute inset-0 w-full h-full object-cover"
        />

        {crop && (
          <>
            {/* Dim overlay — four rectangles around the crop box */}
            <div
              className="absolute bg-black/60 pointer-events-none"
              style={{ top: 0, left: 0, right: 0, height: `${crop.y * 100}%` }}
            />
            <div
              className="absolute bg-black/60 pointer-events-none"
              style={{
                top: `${(crop.y + crop.h) * 100}%`,
                left: 0,
                right: 0,
                bottom: 0,
              }}
            />
            <div
              className="absolute bg-black/60 pointer-events-none"
              style={{
                top: `${crop.y * 100}%`,
                left: 0,
                width: `${crop.x * 100}%`,
                height: `${crop.h * 100}%`,
              }}
            />
            <div
              className="absolute bg-black/60 pointer-events-none"
              style={{
                top: `${crop.y * 100}%`,
                left: `${(crop.x + crop.w) * 100}%`,
                right: 0,
                height: `${crop.h * 100}%`,
              }}
            />

            {/* Crop box border + move handle */}
            <div
              className="absolute border-2 border-white/80 cursor-move"
              style={{
                left: `${crop.x * 100}%`,
                top: `${crop.y * 100}%`,
                width: `${crop.w * 100}%`,
                height: `${crop.h * 100}%`,
              }}
              onPointerDown={(e) => handlePointerDown(e, "move")}
            >
              {/* Rule of thirds grid */}
              <div className="absolute inset-0 pointer-events-none">
                <div
                  className="absolute bg-white/20"
                  style={{ left: "33.33%", top: 0, bottom: 0, width: 1 }}
                />
                <div
                  className="absolute bg-white/20"
                  style={{ left: "66.66%", top: 0, bottom: 0, width: 1 }}
                />
                <div
                  className="absolute bg-white/20"
                  style={{ top: "33.33%", left: 0, right: 0, height: 1 }}
                />
                <div
                  className="absolute bg-white/20"
                  style={{ top: "66.66%", left: 0, right: 0, height: 1 }}
                />
              </div>
            </div>

            {/* Corner handles */}
            {(["nw", "ne", "sw", "se"] as const).map((corner) => {
              const isLeft = corner.includes("w");
              const isTop = corner.includes("n");
              const cx = isLeft ? crop.x : crop.x + crop.w;
              const cy = isTop ? crop.y : crop.y + crop.h;
              const cursor =
                corner === "nw" || corner === "se"
                  ? "cursor-nwse-resize"
                  : "cursor-nesw-resize";
              return (
                <div
                  key={corner}
                  className={`absolute w-4 h-4 ${cursor} z-10`}
                  style={{
                    left: `calc(${cx * 100}% - 8px)`,
                    top: `calc(${cy * 100}% - 8px)`,
                  }}
                  onPointerDown={(e) => handlePointerDown(e, corner)}
                >
                  <div className="absolute inset-1 bg-white rounded-sm shadow" />
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
