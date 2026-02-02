"use client";

import { useRef, useCallback } from "react";
import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";

export function VideoPlayer() {
  const { outputId, comparisonId, isRendering } = useStore();
  const smartRef = useRef<HTMLVideoElement>(null);
  const compRef = useRef<HTMLVideoElement>(null);

  const hasComparison = !!comparisonId;

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

  if (!outputId) {
    return (
      <div className={`rounded-2xl bg-bg-card-solid border border-border flex items-center justify-center h-48 ${
        isRendering ? "animate-pulse" : ""
      }`}>
        <span className="text-sm text-text-muted">
          {isRendering ? "rendering..." : "output will appear here"}
        </span>
      </div>
    );
  }

  if (!hasComparison) {
    return (
      <video
        key={outputId}
        src={videoUrl(outputId)}
        controls
        autoPlay
        loop
        playsInline
        className="rounded-2xl w-full max-h-[70vh] object-contain shadow-lg"
      />
    );
  }

  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <span className="text-[10px] font-medium text-accent text-center uppercase tracking-widest">smart ramp</span>
        <video
          ref={smartRef}
          key={outputId}
          src={videoUrl(outputId)}
          controls
          autoPlay
          loop
          playsInline
          className="rounded-xl w-full max-h-[70vh] object-contain shadow-lg"
          onPlay={syncPlay}
          onPause={syncPause}
          onSeeked={syncSeek}
        />
      </div>
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <span className="text-[10px] font-medium text-text-muted text-center uppercase tracking-widest">uniform speed</span>
        <video
          ref={compRef}
          key={comparisonId}
          src={videoUrl(comparisonId)}
          loop
          playsInline
          muted
          className="rounded-xl w-full max-h-[70vh] object-contain shadow-lg"
        />
      </div>
    </div>
  );
}
