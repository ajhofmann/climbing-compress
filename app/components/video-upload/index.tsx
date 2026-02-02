"use client";

import { useCallback, useState } from "react";
import { useStore } from "@/lib/store";
import { uploadVideo } from "@/lib/api";

export function VideoUpload() {
  const { videoId, videoInfo, thumbnails, setVideo, setProgress } = useStore();
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = async (file: File) => {
    setProgress(0.05, "Uploading video...");
    try {
      const data = await uploadVideo(file);
      setVideo(data.video_id, data.info, data.thumbnails);
      setProgress(0, `Uploaded ${file.name}`);
    } catch {
      setProgress(0, "Upload failed :(");
    }
  };

  const openPicker = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "video/*";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) handleFile(file);
    };
    input.click();
  };

  if (!videoId) {
    return (
      <div
        onDrop={(e) => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onClick={openPicker}
        className={`rounded-2xl border border-dashed p-10 text-center cursor-pointer transition-all duration-200 ${
          isDragging
            ? "border-accent bg-accent/5 scale-[1.01]"
            : "border-border hover:border-accent/40 hover:bg-bg-card"
        }`}
      >
        <p className="text-sm text-text-muted font-medium">drop a climbing video here</p>
        <p className="text-xs text-text-muted mt-1 opacity-50">or click to browse</p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      {thumbnails.length > 0 && (
        <div className="flex gap-0.5 overflow-hidden rounded-lg shrink-0">
          {thumbnails.slice(0, 5).map((t, i) => (
            <img key={i} src={t} alt={`Video thumbnail ${i + 1}`} className="h-10 w-14 object-cover" />
          ))}
        </div>
      )}
      <span className="text-xs text-text-muted font-mono truncate flex-1">
        {videoInfo && `${videoInfo.duration.toFixed(0)}s · ${videoInfo.width}×${videoInfo.height} · ${videoInfo.fps.toFixed(0)}fps`}
      </span>
      <button onClick={openPicker} className="text-xs text-accent hover:underline shrink-0">
        change
      </button>
    </div>
  );
}
