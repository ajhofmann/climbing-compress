"use client";

import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";

export function VideoPlayer() {
  const { outputId, isRendering } = useStore();

  if (!outputId) {
    return (
      <div className={`rounded-2xl bg-bg-card border border-border flex flex-col items-center justify-center h-48 gap-2 ${
        isRendering ? "animate-pulse" : ""
      }`}>
        <span className="text-2xl">{isRendering ? "🎬" : "📼"}</span>
        <span className="text-sm text-text-muted">
          {isRendering ? "rendering your send..." : "output will appear here"}
        </span>
      </div>
    );
  }

  return (
    <video
      key={outputId}
      src={videoUrl(outputId)}
      controls
      autoPlay
      loop
      playsInline
      className="rounded-2xl w-full shadow-lg"
    />
  );
}
