"use client";

import { useRef, useCallback, useEffect } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";

export function VideoPlayer() {
  const outputId = useStore((state) => state.outputId);
  const comparisonId = useStore((state) => state.comparisonId);
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
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [outputId, togglePlayback, seekBy]);

  if (!outputId) return null;

  if (!hasComparison) {
    return (
      <div className="neon-video-frame overflow-hidden">
        <video
          ref={singleRef}
          key={outputId}
          src={videoUrl(outputId)}
          controls
          autoPlay
          loop
          playsInline
          onTimeUpdate={onTimeUpdate}
          className="w-full max-h-[70vh] object-contain"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <span className="text-[10px] font-pixel text-center uppercase tracking-[0.2em]" style={{ color: "var(--neon-cyan)", textShadow: "0 0 6px rgba(0,229,255,0.4)" }}>smart ramp</span>
        <div className="neon-video-frame overflow-hidden">
          <video
            ref={smartRef}
            key={outputId}
            src={videoUrl(outputId)}
            controls
            autoPlay
            loop
            playsInline
            className="w-full max-h-[70vh] object-contain"
            onPlay={syncPlay}
            onPause={syncPause}
            onSeeked={syncSeek}
            onTimeUpdate={onTimeUpdate}
          />
        </div>
      </div>
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <span className="text-[10px] font-pixel text-center uppercase tracking-[0.2em]" style={{ color: "var(--text-muted)" }}>uniform speed</span>
        <div className="neon-video-frame overflow-hidden" style={{ borderColor: "rgba(224,64,251,0.08)", boxShadow: "0 0 15px rgba(224,64,251,0.05)" }}>
          <video
            ref={compRef}
            key={comparisonId}
            src={videoUrl(comparisonId)}
            loop
            playsInline
            muted
            className="w-full max-h-[70vh] object-contain"
          />
        </div>
      </div>
    </div>
  );
}
