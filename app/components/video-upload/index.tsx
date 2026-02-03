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
        className={`rounded retro-panel px-4 py-2 cursor-pointer transition-all duration-200 ${
          isDragging ? "marching-ants" : ""
        }`}
        style={isDragging ? {
          boxShadow: "0 0 20px rgba(0,229,255,0.3), inset 0 0 30px rgba(0,229,255,0.05)",
          borderColor: "var(--neon-cyan)",
        } : {}}
      >
        <div className="flex items-center justify-center gap-3">
          <span className="text-xs font-pixel text-neon-cyan retro-glow tracking-wide uppercase">
            {">> DROP VID OR CLICK <<"}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 retro-panel rounded px-3 py-2">
      {thumbnails.length > 0 && (
        <div className="flex gap-0.5 overflow-hidden rounded shrink-0 crt-filter">
          {thumbnails.slice(0, 5).map((t, i) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={i} src={t} alt={`Thumb ${i + 1}`} className="h-10 w-14 object-cover" />
          ))}
        </div>
      )}
      <span className="text-sm font-retro led-text truncate flex-1">
        {videoInfo && `${videoInfo.duration.toFixed(0)}s // ${videoInfo.width}x${videoInfo.height} // ${videoInfo.fps.toFixed(0)}fps`}
      </span>
      <button onClick={openPicker} className="text-sm font-pixel text-neon-magenta hover:text-white retro-glow-magenta shrink-0 uppercase">
        [CHANGE]
      </button>
    </div>
  );
}
