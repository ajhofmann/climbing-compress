"use client";

import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { deleteAllVideos, deleteVideo, getVideoMeta, listVideos, renameVideo, uploadVideo, VideoListItem } from "@/lib/api";
import { Tooltip } from "@/components/tooltip";

const SUPPORTED_VIDEO_EXTS = [".mov", ".mp4", ".avi", ".mkv"] as const;

export function VideoUpload() {
  const videoId = useStore((state) => state.videoId);
  const videoName = useStore((state) => state.videoName);
  const videoInfo = useStore((state) => state.videoInfo);
  const setVideo = useStore((state) => state.setVideo);
  const setVideoName = useStore((state) => state.setVideoName);
  const clearVideo = useStore((state) => state.clearVideo);
  const setProgress = useStore((state) => state.setProgress);
  const progressMessage = useStore((state) => state.progressMessage);
  const isAnalyzing = useStore((state) => state.isAnalyzing);
  const isRendering = useStore((state) => state.isRendering);
  const [isDragging, setIsDragging] = useState(false);
  const [recentVideos, setRecentVideos] = useState<VideoListItem[]>([]);
  const [deletingVideoId, setDeletingVideoId] = useState<string | null>(null);
  const [renamingVideoId, setRenamingVideoId] = useState<string | null>(null);
  const [recentFetchDone, setRecentFetchDone] = useState(false);
  const [refreshingRecent, setRefreshingRecent] = useState(false);
  const [clearingLibrary, setClearingLibrary] = useState(false);

  const shortName = (name: string) => {
    if (name.length <= 14) return name;
    const dot = name.lastIndexOf(".");
    if (dot <= 0 || dot === name.length - 1) {
      return `${name.slice(0, 8)}…${name.slice(-4)}`;
    }
    const stem = name.slice(0, dot);
    const ext = name.slice(dot);
    if (stem.length <= 8) return name;
    return `${stem.slice(0, 6)}…${ext}`;
  };

  useEffect(() => {
    if (videoId) return;
    let cancelled = false;
    void listVideos()
      .then((items) => {
        if (cancelled) return;
        setRecentVideos(items.slice(0, 6));
        setRecentFetchDone(true);
      })
      .catch(() => {
        if (cancelled) return;
        setRecentVideos([]);
        setRecentFetchDone(true);
      })
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  const refreshRecent = async () => {
    setRefreshingRecent(true);
    try {
      const items = await listVideos();
      setRecentVideos(items.slice(0, 6));
    } catch {
      setRecentVideos([]);
    } finally {
      setRecentFetchDone(true);
      setRefreshingRecent(false);
    }
  };

  const handleFile = async (file: File) => {
    const ext = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase()}` : "";
    if (!SUPPORTED_VIDEO_EXTS.includes(ext as typeof SUPPORTED_VIDEO_EXTS[number])) {
      setProgress(0, `Unsupported file type (${ext || "unknown"}). Use ${SUPPORTED_VIDEO_EXTS.join(", ")}`);
      return;
    }
    setProgress(0.05, "Uploading video...");
    try {
      const data = await uploadVideo(file);
      setVideo(data.video_id, data.info, data.thumbnails, data.filename);
      const cacheHint = data.cached ? " (analysis cached)" : "";
      const label = data.filename || file.name;
      const status = data.reused ? `Loaded existing clip ${label}` : `Uploaded ${label}`;
      setProgress(0, `${status}${cacheHint}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setProgress(0, `Upload failed: ${msg}`);
    }
  };

  const handleLoadExisting = async (item: VideoListItem) => {
    if (deletingVideoId || renamingVideoId || clearingLibrary) return;
    setProgress(0.05, `Loading ${item.filename}...`);
    try {
      const meta = await getVideoMeta(item.video_id);
      setVideo(meta.video_id, meta.info, meta.thumbnails, meta.filename);
      setProgress(0, `Loaded ${meta.filename}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Load failed";
      setProgress(0, `Load failed: ${msg}`);
    }
  };

  const runRename = async (targetId: string, currentName: string) => {
    const nextRaw = window.prompt("Rename clip", currentName);
    if (nextRaw === null) return;
    const next = nextRaw.trim().split(/[/\\]/).pop() ?? "";
    if (!next) return;
    const currentExt = currentName.includes(".") ? `.${currentName.split(".").pop()?.toLowerCase()}` : "";
    const impliedName = next.includes(".") ? next : `${next}${currentExt}`;
    if (impliedName.toLowerCase() === currentName.toLowerCase()) return;
    if (next.length > 120) {
      setProgress(0, "Rename failed: filename too long (max 120 chars)");
      return;
    }
    const ext = next.includes(".") ? `.${next.split(".").pop()?.toLowerCase()}` : "";
    if (ext && !SUPPORTED_VIDEO_EXTS.includes(ext as typeof SUPPORTED_VIDEO_EXTS[number])) {
      setProgress(0, `Rename failed: unsupported extension ${ext}`);
      return;
    }
    setRenamingVideoId(targetId);
    try {
      const renamed = await renameVideo(targetId, next);
      setRecentVideos((prev) => prev.map((item) => (
        item.video_id === targetId
          ? { ...item, filename: renamed.filename }
          : item
      )));
      if (videoId === targetId) setVideoName(renamed.filename);
      setProgress(0, `Renamed ${currentName} → ${renamed.filename}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Rename failed";
      setProgress(0, `Rename failed: ${msg}`);
    } finally {
      setRenamingVideoId(null);
    }
  };

  const handleRenameExisting = async (item: VideoListItem) => {
    if (deletingVideoId || renamingVideoId || clearingLibrary) return;
    await runRename(item.video_id, item.filename);
  };

  const handleDeleteExisting = async (item: VideoListItem) => {
    if (deletingVideoId || renamingVideoId || clearingLibrary) return;
    const confirmed = window.confirm(`Remove ${item.filename} from your local library?`);
    if (!confirmed) return;
    setDeletingVideoId(item.video_id);
    try {
      await deleteVideo(item.video_id);
      await refreshRecent();
      setProgress(0, `Removed ${item.filename}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setProgress(0, `Delete failed: ${msg}`);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleClearLibrary = async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary) return;
    const confirmed = window.confirm("Remove all local clips from this library?");
    if (!confirmed) return;
    const shouldClearCurrent = Boolean(videoId);
    setClearingLibrary(true);
    try {
      const result = await deleteAllVideos();
      setRecentVideos([]);
      setRecentFetchDone(true);
      if (shouldClearCurrent) clearVideo();
      const count = result.deleted ?? 0;
      if (count <= 0) {
        setProgress(0, "Local library already empty.");
      } else if (count === 1) {
        setProgress(0, "Removed 1 local clip.");
      } else {
        setProgress(0, `Removed ${count} local clips.`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear failed";
      setProgress(0, `Clear failed: ${msg}`);
    } finally {
      setClearingLibrary(false);
    }
  };

  const openPicker = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = SUPPORTED_VIDEO_EXTS.join(",");
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) handleFile(file);
    };
    input.click();
  };

  const handleClearVideo = () => {
    if (isAnalyzing || isRendering) return;
    clearVideo();
    setProgress(0, "Clip cleared. Pick another video or use Recent.");
  };

  const handleDeleteCurrent = async () => {
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary) return;
    const label = videoName || "current clip";
    const confirmed = window.confirm(`Remove ${label} from your local library?`);
    if (!confirmed) return;
    setDeletingVideoId(videoId);
    try {
      await deleteVideo(videoId);
      await refreshRecent();
      clearVideo();
      setProgress(0, `Removed ${label} from local library.`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setProgress(0, `Delete failed: ${msg}`);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleRenameCurrent = async () => {
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary) return;
    await runRename(videoId, videoName || "clip.mp4");
  };

  if (!videoId) {
    return (
      <div
        onDrop={(e) => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openPicker();
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload climbing video"
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
        {recentFetchDone && (
          <div
            className="w-full px-4 pt-1 flex flex-col gap-1"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-center gap-2">
              <span className="text-[10px] font-pixel uppercase tracking-widest text-text-muted text-center">
                Recent ({recentVideos.length})
              </span>
              <button
                onClick={() => void refreshRecent()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
              >
                {refreshingRecent ? "[refreshing...]" : "[refresh]"}
              </button>
              <button
                onClick={() => void handleClearLibrary()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || recentVideos.length === 0}
                className="text-[9px] font-pixel text-magenta-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
              >
                {clearingLibrary ? "[clearing...]" : "[clear all]"}
              </button>
            </div>
            {recentVideos.length > 0 ? (
              <div className="flex flex-wrap justify-center gap-1">
                {recentVideos.map((item) => (
                  <div key={item.video_id} className="flex items-center gap-0.5">
                    <button
                      onClick={() => void handleLoadExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary}
                      className="retro-btn px-2 py-0.5 text-[10px] font-pixel tracking-wide max-w-[180px] truncate disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`${item.filename} · ${item.info.duration.toFixed(1)}s${item.cached ? " · cached analysis" : ""}`}
                    >
                      {item.cached ? "⚡ " : ""}
                      {shortName(item.filename)}
                    </button>
                    <button
                      onClick={() => void handleRenameExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary}
                      className="text-[10px] font-pixel px-1 py-0.5 border rounded border-cyan-400/40 text-cyan-200 hover:text-white hover:border-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`Rename ${item.filename}`}
                      aria-label={`Rename ${item.filename}`}
                    >
                      ✎
                    </button>
                    <button
                      onClick={() => void handleDeleteExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary}
                      className="text-[10px] font-pixel px-1 py-0.5 border rounded border-magenta-400/40 text-magenta-200 hover:text-white hover:border-magenta-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`Remove ${item.filename}`}
                      aria-label={`Remove ${item.filename} from local library`}
                    >
                      X
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-[10px] font-pixel text-text-muted/70 text-center">no local clips</span>
            )}
          </div>
        )}
        {progressMessage && (
          <span className="text-[10px] font-pixel text-cyan-300/70 text-center mt-1 block max-w-full truncate px-2">
            {progressMessage}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      {videoName && (
        <span
          className="text-[11px] font-pixel text-text-muted max-w-[170px] truncate"
          title={videoName}
        >
          {videoName}
        </span>
      )}
      <span className="text-[11px] font-retro led-text whitespace-nowrap">
        {videoInfo && `${videoInfo.duration.toFixed(0)}s / ${videoInfo.width}x${videoInfo.height} / ${videoInfo.fps.toFixed(0)}fps`}
      </span>
      <Tooltip text="Clear current clip and return to upload/recent selector">
        <button
          onClick={handleClearVideo}
          disabled={isAnalyzing || isRendering}
          className="text-[11px] font-pixel text-text-muted hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [EJECT]
        </button>
      </Tooltip>
      <Tooltip text="Replace the current video with a new one">
        <button onClick={openPicker} className="text-[11px] font-pixel text-neon-magenta hover:text-white retro-glow-magenta shrink-0 uppercase">
          [SWAP]
        </button>
      </Tooltip>
      <Tooltip text="Delete this clip from local library and clear the current session">
        <button
          onClick={() => void handleDeleteCurrent()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [DELETE]
        </button>
      </Tooltip>
      <Tooltip text="Rename current clip label in local library">
        <button
          onClick={() => void handleRenameCurrent()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary}
          className="text-[11px] font-pixel text-cyan-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [RENAME]
        </button>
      </Tooltip>
      <Tooltip text="Remove every clip from local library and reset to upload screen">
        <button
          onClick={() => void handleClearLibrary()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [CLEAR LIB]
        </button>
      </Tooltip>
    </div>
  );
}
