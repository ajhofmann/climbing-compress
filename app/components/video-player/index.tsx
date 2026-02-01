"use client";

import { useStore } from "@/lib/store";
import { videoUrl } from "@/lib/api";

export function VideoPlayer() {
  const { outputId, isRendering } = useStore();

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
