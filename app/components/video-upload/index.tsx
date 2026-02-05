"use client";

import { useCallback, useState } from "react";
import { useStore } from "@/lib/store";
import { uploadVideo } from "@/lib/api";
import { Tooltip } from "@/components/tooltip";

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
        className={`relative rounded cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-2 ${
          isDragging ? "marching-ants" : "drop-zone-glow"
        }`}
        style={{
          minHeight: 100,
          background: "linear-gradient(180deg, rgba(0,229,255,0.02) 0%, transparent 60%)",
          ...(isDragging ? {
            boxShadow: "0 0 30px rgba(0,229,255,0.3), inset 0 0 40px rgba(0,229,255,0.05)",
            borderColor: "var(--neon-cyan)",
          } : {}),
        }}
      >
        {/* Corner brackets */}
        <svg className="absolute top-1.5 left-1.5 opacity-20" width="14" height="14">
          <polyline points="0,10 0,0 10,0" stroke="#00e5ff" strokeWidth="1" fill="none" />
        </svg>
        <svg className="absolute top-1.5 right-1.5 opacity-20" width="14" height="14">
          <polyline points="14,10 14,0 4,0" stroke="#00e5ff" strokeWidth="1" fill="none" />
        </svg>
        <svg className="absolute bottom-1.5 left-1.5 opacity-15" width="14" height="14">
          <polyline points="0,4 0,14 10,14" stroke="#e040fb" strokeWidth="1" fill="none" />
        </svg>
        <svg className="absolute bottom-1.5 right-1.5 opacity-15" width="14" height="14">
          <polyline points="14,4 14,14 4,14" stroke="#e040fb" strokeWidth="1" fill="none" />
        </svg>

        <span className="text-xs font-pixel led-text tracking-widest">
          {">> DROP VIDEO OR CLICK TO START <<"}
        </span>
        <span className="text-sm font-retro text-text-muted">[ or click to browse ]</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      <span className="text-[11px] font-retro led-text whitespace-nowrap">
        {videoInfo && `${videoInfo.duration.toFixed(0)}s / ${videoInfo.width}x${videoInfo.height} / ${videoInfo.fps.toFixed(0)}fps`}
      </span>
      <Tooltip text="Replace the current video with a new one">
        <button onClick={openPicker} className="text-[11px] font-pixel text-neon-magenta hover:text-white retro-glow-magenta shrink-0 uppercase">
          [SWAP]
        </button>
      </Tooltip>
    </div>
  );
}
