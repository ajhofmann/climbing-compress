"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";
import { VcrTransport, OsdFlash, LiveTimecode } from "./transport";

export function VideoPlayer() {
  const outputId = useStore((state) => state.outputId);
  const comparisonId = useStore((state) => state.comparisonId);
  const outputFps = useStore((state) => state.settings.outputFps);
  const setPlaybackTime = useStore((state) => state.setPlaybackTime);
  const compRef = useRef<HTMLVideoElement | null>(null);
  const [primaryEl, setPrimaryEl] = useState<HTMLVideoElement | null>(null);
  const [compEl, setCompEl] = useState<HTMLVideoElement | null>(null);
  const primaryRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => { primaryRef.current = primaryEl; }, [primaryEl]);
  const bindCompEl = useCallback((el: HTMLVideoElement | null) => {
    compRef.current = el;
    setCompEl(el);
  }, []);
  const [osd, setOsd] = useState<{ label: string; key: number } | null>(null);

  const hasComparison = !!comparisonId;

  const flashOsd = useCallback((label: string) => {
    setOsd((prev) => ({ label, key: (prev?.key ?? 0) + 1 }));
  }, []);

  // Track playback position → store (for chart tracker)
  const onTimeUpdate = useCallback(() => {
    if (primaryEl) setPlaybackTime(primaryEl.currentTime);
  }, [primaryEl, setPlaybackTime]);

  // Reset playback time + stale OSD when output changes
  useEffect(() => { setPlaybackTime(0); }, [outputId, setPlaybackTime]);
  const [prevOutputId, setPrevOutputId] = useState(outputId);
  if (prevOutputId !== outputId) {
    setPrevOutputId(outputId);
    setOsd(null);
  }

  // Sync both videos: when one plays/pauses/seeks, mirror to the other
  const syncPlay = useCallback(() => {
    void compRef.current?.play().catch(() => {});
  }, []);
  const syncPause = useCallback(() => {
    compRef.current?.pause();
  }, []);
  const syncSeek = useCallback(() => {
    if (primaryRef.current && compRef.current) {
      compRef.current.currentTime = primaryRef.current.currentTime;
    }
  }, []);

  const safePlay = useCallback((video: HTMLVideoElement | null) => {
    if (!video) return;
    void video.play().catch(() => {
      // Ignore autoplay/play promise interruptions.
    });
  }, []);

  const togglePlayback = useCallback(() => {
    const v = primaryRef.current;
    if (!v) return;
    if (v.paused) {
      safePlay(v);
      if (hasComparison) safePlay(compRef.current);
      flashOsd("▶ PLAY");
    } else {
      v.pause();
      compRef.current?.pause();
      flashOsd("❚❚ PAUSE");
    }
  }, [hasComparison, safePlay, flashOsd]);

  const seekBy = useCallback((deltaSeconds: number) => {
    const v = primaryRef.current;
    if (!v) return;
    const duration = Number.isFinite(v.duration) ? v.duration : 0;
    const next = Math.max(0, Math.min(duration || v.currentTime + deltaSeconds, v.currentTime + deltaSeconds));
    v.currentTime = next;
    if (compRef.current) {
      compRef.current.currentTime = v.currentTime;
    }
    flashOsd(deltaSeconds < 0 ? "◀◀ REW" : "▶▶ FF");
  }, [flashOsd]);

  const stepFrame = useCallback((direction: -1 | 1, frames: number = 1) => {
    const fps = Math.max(1, outputFps);
    const v = primaryRef.current;
    if (!v) return;
    v.pause();
    compRef.current?.pause();
    const duration = Number.isFinite(v.duration) ? v.duration : 0;
    const delta = (direction * frames) / fps;
    const next = Math.max(0, Math.min(duration || v.currentTime + delta, v.currentTime + delta));
    v.currentTime = next;
    if (compRef.current) compRef.current.currentTime = next;
    flashOsd(direction > 0 ? "❚▶ STEP" : "◀❚ STEP");
  }, [outputFps, flashOsd]);

  useEffect(() => {
    if (!outputId) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.repeat) return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      if (target?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON") return;

      const key = e.key.toLowerCase();
      if (e.code === "Space" || key === "k") {
        e.preventDefault();
        togglePlayback();
        return;
      }
      if (key === "j") {
        e.preventDefault();
        seekBy(-1);
        return;
      }
      if (key === "l") {
        e.preventDefault();
        seekBy(1);
        return;
      }
      if (e.key === ",") {
        e.preventDefault();
        stepFrame(-1, e.shiftKey ? 5 : 1);
        return;
      }
      if (e.key === ".") {
        e.preventDefault();
        stepFrame(1, e.shiftKey ? 5 : 1);
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [outputId, togglePlayback, seekBy, stepFrame]);

  if (!outputId) return null;

  if (!hasComparison) {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="vcr-status text-sm">▶ PLAY</span>
          <span className="vcr-osd text-sm text-text-muted/60">
            ◀◀ J &nbsp; ▶❚❚ K &nbsp; ▶▶ L &nbsp; ◀ , &nbsp; ▶ .
          </span>
        </div>
        <div className="neon-video-frame overflow-hidden crt-scanlines vhs-tracking relative">
          <video
            ref={setPrimaryEl}
            key={outputId}
            src={videoUrl(outputId)}
            autoPlay
            loop
            playsInline
            aria-label="Rendered climb video (keyboard: J/K/L, comma/period frame step, Space)"
            aria-keyshortcuts="J K L Comma Period Space"
            onTimeUpdate={onTimeUpdate}
            onClick={togglePlayback}
            className="w-full max-h-[70vh] object-contain cursor-pointer"
          />
          {/* VCR OSD overlay */}
          <div className="absolute top-3 left-4 pointer-events-none z-10 flex items-center gap-3">
            <span className="vcr-osd text-sm">SENDIT</span>
            <span className="vcr-osd text-sm text-text-muted/50">SP</span>
            <OsdFlash flash={osd} />
          </div>
          <div className="absolute top-3 right-4 pointer-events-none z-10">
            <span className="tape-counter text-sm">{outputId.slice(0, 8)}</span>
          </div>
          <div className="absolute bottom-3 left-4 pointer-events-none z-10">
            <LiveTimecode videoEl={primaryEl} className="text-sm" />
          </div>
        </div>
        <VcrTransport videoEl={primaryEl} fps={outputFps} onOsd={flashOsd} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex flex-col gap-1.5 flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="vcr-status text-sm">▶ SMART RAMP</span>
            <span className="vcr-osd text-sm text-text-muted/50">◀◀ J · ▶❚❚ K · ▶▶ L</span>
          </div>
          <div className="neon-video-frame overflow-hidden crt-scanlines vhs-tracking relative">
            <video
              ref={setPrimaryEl}
              key={outputId}
              src={videoUrl(outputId)}
              autoPlay
              loop
              playsInline
              aria-label="Rendered climb video smart ramp comparison (keyboard: J/K/L, comma/period frame step, Space)"
              aria-keyshortcuts="J K L Comma Period Space"
              className="w-full max-h-[70vh] object-contain cursor-pointer"
              onPlay={syncPlay}
              onPause={syncPause}
              onSeeked={syncSeek}
              onTimeUpdate={onTimeUpdate}
              onClick={togglePlayback}
            />
            <div className="absolute top-3 left-4 pointer-events-none z-10 flex items-center gap-3">
              <span className="vcr-osd text-sm">SENDIT · SP</span>
              <OsdFlash flash={osd} />
            </div>
            <div className="absolute bottom-3 left-4 pointer-events-none z-10">
              <LiveTimecode videoEl={primaryEl} className="text-sm" />
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-1.5 flex-1 min-w-0">
          <span className="vcr-osd text-sm text-text-muted/50 text-center">UNIFORM SPEED</span>
          <div className="neon-video-frame overflow-hidden crt-scanlines relative" style={{ borderColor: "rgba(224,64,251,0.08)", boxShadow: "0 0 15px rgba(224,64,251,0.05)" }}>
            <video
              ref={bindCompEl}
              key={comparisonId}
              src={videoUrl(comparisonId)}
              loop
              playsInline
              muted
              aria-hidden="true"
              className="w-full max-h-[70vh] object-contain"
            />
            <div className="absolute top-3 right-4 pointer-events-none z-10">
              <span className="vcr-osd text-sm text-text-muted/40">REF</span>
            </div>
          </div>
        </div>
      </div>
      <VcrTransport videoEl={primaryEl} syncEl={compEl} fps={outputFps} onOsd={flashOsd} />
    </div>
  );
}
