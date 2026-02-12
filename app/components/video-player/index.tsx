"use client";

import { useRef, useCallback, useEffect } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";

export function VideoPlayer() {
  const outputId = useStore((state) => state.outputId);
  const comparisonId = useStore((state) => state.comparisonId);
  const outputFps = useStore((state) => state.settings.outputFps);
  const setPlaybackTime = useStore((state) => state.setPlaybackTime);
  const smartRef = useRef<HTMLVideoElement>(null);
  const compRef = useRef<HTMLVideoElement>(null);
  const singleRef = useRef<HTMLVideoElement>(null);

  const hasComparison = !!comparisonId;

  // Track playback position → store (for chart tracker)
  const onTimeUpdate = useCallback(() => {
    const vid = smartRef.current ?? singleRef.current;
    if (vid) setPlaybackTime(vid.currentTime);
  }, [setPlaybackTime]);

  // Reset playback time when output changes
  useEffect(() => { setPlaybackTime(0); }, [outputId, setPlaybackTime]);

  // Sync both videos: when one plays/pauses/seeks, mirror to the other
  const syncPlay = useCallback(() => {
    compRef.current?.play();
  }, []);
  const syncPause = useCallback(() => {
    compRef.current?.pause();
  }, []);
  const syncSeek = useCallback(() => {
    if (smartRef.current && compRef.current) {
      compRef.current.currentTime = smartRef.current.currentTime;
    }
  }, []);

  const safePlay = useCallback((video: HTMLVideoElement | null) => {
    if (!video) return;
    void video.play().catch(() => {
      // Ignore autoplay/play promise interruptions.
    });
  }, []);

  const togglePlayback = useCallback(() => {
    const primary = smartRef.current ?? singleRef.current;
    if (!primary) return;
    if (primary.paused) {
      safePlay(primary);
      if (smartRef.current && compRef.current) safePlay(compRef.current);
    } else {
      primary.pause();
      if (compRef.current) compRef.current.pause();
    }
  }, [safePlay]);

  const seekBy = useCallback((deltaSeconds: number) => {
    const primary = smartRef.current ?? singleRef.current;
    if (!primary) return;
    const duration = Number.isFinite(primary.duration) ? primary.duration : 0;
    const next = Math.max(0, Math.min(duration || primary.currentTime + deltaSeconds, primary.currentTime + deltaSeconds));
    primary.currentTime = next;
    if (smartRef.current && compRef.current) {
      compRef.current.currentTime = smartRef.current.currentTime;
    }
  }, []);

  const stepFrame = useCallback((direction: -1 | 1, frames: number = 1) => {
    const fps = Math.max(1, outputFps);
    seekBy((direction * frames) / fps);
  }, [outputFps, seekBy]);

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
            ref={singleRef}
            key={outputId}
            src={videoUrl(outputId)}
            controls
            autoPlay
            loop
            playsInline
            aria-label="Rendered climb video (keyboard: J/K/L, comma/period frame step, Space)"
            aria-keyshortcuts="J K L Comma Period Space"
            onTimeUpdate={onTimeUpdate}
            className="w-full max-h-[70vh] object-contain"
          />
          {/* VCR OSD overlay */}
          <div className="absolute top-3 left-4 pointer-events-none z-10 flex items-center gap-2">
            <span className="vcr-osd text-sm">SENDIT</span>
            <span className="vcr-osd text-sm text-text-muted/50">SP</span>
          </div>
          <div className="absolute top-3 right-4 pointer-events-none z-10">
            <span className="tape-counter text-sm">{outputId.slice(0, 8)}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <div className="flex flex-col gap-1.5 flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="vcr-status text-sm">▶ SMART RAMP</span>
          <span className="vcr-osd text-sm text-text-muted/50">◀◀ J · ▶❚❚ K · ▶▶ L</span>
        </div>
        <div className="neon-video-frame overflow-hidden crt-scanlines vhs-tracking relative">
          <video
            ref={smartRef}
            key={outputId}
            src={videoUrl(outputId)}
            controls
            autoPlay
            loop
            playsInline
            aria-label="Rendered climb video smart ramp comparison (keyboard: J/K/L, comma/period frame step, Space)"
            aria-keyshortcuts="J K L Comma Period Space"
            className="w-full max-h-[70vh] object-contain"
            onPlay={syncPlay}
            onPause={syncPause}
            onSeeked={syncSeek}
            onTimeUpdate={onTimeUpdate}
          />
          <div className="absolute top-3 left-4 pointer-events-none z-10">
            <span className="vcr-osd text-sm">SENDIT · SP</span>
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-1.5 flex-1 min-w-0">
        <span className="vcr-osd text-sm text-text-muted/50 text-center">UNIFORM SPEED</span>
        <div className="neon-video-frame overflow-hidden crt-scanlines relative" style={{ borderColor: "rgba(224,64,251,0.08)", boxShadow: "0 0 15px rgba(224,64,251,0.05)" }}>
          <video
            ref={compRef}
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
  );
}
