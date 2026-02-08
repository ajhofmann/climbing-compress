"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { deleteAllOutputs, deleteAllVideos, deleteVideo, getLibraryStats, getVideoMeta, listVideos, renameVideo, uploadVideo, VideoListItem } from "@/lib/api";
import { Tooltip } from "@/components/tooltip";

const SUPPORTED_VIDEO_EXTS = [".mov", ".mp4", ".avi", ".mkv"] as const;
const RECENT_PREVIEW_LIMIT = 6;
const RECENT_PREF_KEY = "sendit.recentPrefs";

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
  const [clearingOutputs, setClearingOutputs] = useState(false);
  const [outputCount, setOutputCount] = useState<number | null>(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [recentFilter, setRecentFilter] = useState("");
  const [recentSort, setRecentSort] = useState<"recent" | "name" | "duration">("recent");
  const recentFilterInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(RECENT_PREF_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { sort?: string; showAll?: boolean };
      if (parsed.sort === "recent" || parsed.sort === "name" || parsed.sort === "duration") {
        setRecentSort(parsed.sort);
      }
      if (typeof parsed.showAll === "boolean") {
        setShowAllRecent(parsed.showAll);
      }
    } catch {
      // ignore malformed local preferences
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(RECENT_PREF_KEY, JSON.stringify({
        sort: recentSort,
        showAll: showAllRecent,
      }));
    } catch {
      // ignore storage write failures
    }
  }, [recentSort, showAllRecent]);

  useEffect(() => {
    if (videoId || !recentFetchDone) return;
    const onGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (!recentFilter) return;
        e.preventDefault();
        setRecentFilter("");
        recentFilterInputRef.current?.blur();
        return;
      }
      if (e.key !== "/") return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || target?.isContentEditable) return;
      e.preventDefault();
      recentFilterInputRef.current?.focus();
    };
    window.addEventListener("keydown", onGlobalKeyDown, true);
    return () => window.removeEventListener("keydown", onGlobalKeyDown, true);
  }, [videoId, recentFetchDone, recentFilter]);

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

  const formatDuration = (seconds: number) => {
    if (!Number.isFinite(seconds) || seconds <= 0) return "0:00";
    const total = Math.round(seconds);
    const hours = Math.floor(total / 3600);
    const mins = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours > 0) return `${hours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const applyRecent = (items: VideoListItem[]) => {
    setRecentVideos(items);
    setShowAllRecent((prev) => (items.length > RECENT_PREVIEW_LIMIT ? prev : false));
  };

  const normalizedRecentFilter = recentFilter.trim().toLowerCase();
  const filteredRecent = useMemo(() => (
    normalizedRecentFilter
      ? recentVideos.filter((item) => item.filename.toLowerCase().includes(normalizedRecentFilter))
      : recentVideos
  ), [recentVideos, normalizedRecentFilter]);

  const sortedRecent = useMemo(() => (
    recentSort === "recent"
      ? filteredRecent
      : [...filteredRecent].sort((a, b) => {
        if (recentSort === "name") return a.filename.localeCompare(b.filename, undefined, { sensitivity: "base" });
        const byDuration = b.info.duration - a.info.duration;
        if (Math.abs(byDuration) > 1e-6) return byDuration;
        return a.filename.localeCompare(b.filename, undefined, { sensitivity: "base" });
      })
  ), [filteredRecent, recentSort]);

  const visibleRecent = useMemo(() => (
    showAllRecent
      ? sortedRecent
      : sortedRecent.slice(0, RECENT_PREVIEW_LIMIT)
  ), [showAllRecent, sortedRecent]);
  const hiddenRecentCount = Math.max(0, sortedRecent.length - visibleRecent.length);
  const totalRecentDuration = useMemo(
    () => recentVideos.reduce((sum, item) => sum + item.info.duration, 0),
    [recentVideos],
  );
  const filteredRecentDuration = useMemo(
    () => filteredRecent.reduce((sum, item) => sum + item.info.duration, 0),
    [filteredRecent],
  );

  useEffect(() => {
    if (videoId) return;
    let cancelled = false;
    void Promise.allSettled([listVideos(), getLibraryStats()])
      .then(([videosRes, statsRes]) => {
        if (cancelled) return;
        if (videosRes.status === "fulfilled") {
          applyRecent(videosRes.value);
        } else {
          applyRecent([]);
        }
        if (statsRes.status === "fulfilled") {
          setOutputCount(statsRes.value.outputs);
        } else {
          setOutputCount(null);
        }
        setRecentFetchDone(true);
      })
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  const refreshRecent = async () => {
    setRefreshingRecent(true);
    try {
      const [videosRes, statsRes] = await Promise.allSettled([listVideos(), getLibraryStats()]);
      if (videosRes.status === "fulfilled") {
        applyRecent(videosRes.value);
      } else {
        applyRecent([]);
      }
      if (statsRes.status === "fulfilled") {
        setOutputCount(statsRes.value.outputs);
      } else {
        setOutputCount(null);
      }
    } catch {
      applyRecent([]);
      setOutputCount(null);
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
    if (deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
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
    if (deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
    await runRename(item.video_id, item.filename);
  };

  const handleDeleteExisting = async (item: VideoListItem) => {
    if (deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
    const confirmed = window.confirm(`Remove ${item.filename} from your local library?`);
    if (!confirmed) return;
    setDeletingVideoId(item.video_id);
    try {
      const result = await deleteVideo(item.video_id);
      await refreshRecent();
      const outputs = result.deleted_outputs ?? 0;
      if (outputs > 0) {
        setOutputCount((prev) => (prev == null ? null : Math.max(0, prev - outputs)));
      }
      const outputPart = outputs <= 0
        ? ""
        : outputs === 1
          ? " Cleared 1 rendered output."
          : ` Cleared ${outputs} rendered outputs.`;
      setProgress(0, `Removed ${item.filename}.${outputPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setProgress(0, `Delete failed: ${msg}`);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleClearLibrary = async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
    const confirmed = window.confirm("Remove all local clips from this library?");
    if (!confirmed) return;
    const shouldClearCurrent = Boolean(videoId);
    setClearingLibrary(true);
    try {
      const result = await deleteAllVideos();
      setRecentVideos([]);
      setShowAllRecent(false);
      setRecentFetchDone(true);
      setOutputCount(0);
      if (shouldClearCurrent) clearVideo();
      const count = result.deleted ?? 0;
      const outputs = result.deleted_outputs ?? 0;
      const clipPart = count <= 0
        ? "Local library already empty."
        : count === 1
          ? "Removed 1 local clip."
          : `Removed ${count} local clips.`;
      const outputPart = outputs <= 0
        ? ""
        : outputs === 1
          ? " Cleared 1 rendered output."
          : ` Cleared ${outputs} rendered outputs.`;
      setProgress(0, `${clipPart}${outputPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear failed";
      setProgress(0, `Clear failed: ${msg}`);
    } finally {
      setClearingLibrary(false);
    }
  };

  const handleClearOutputs = async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
    const confirmed = window.confirm("Remove all rendered outputs? (keeps source clips)");
    if (!confirmed) return;
    setClearingOutputs(true);
    try {
      const result = await deleteAllOutputs();
      const outputs = result.deleted_outputs ?? 0;
      setOutputCount(0);
      if (outputs <= 0) {
        setProgress(0, "No rendered outputs to clear.");
      } else if (outputs === 1) {
        setProgress(0, "Cleared 1 rendered output.");
      } else {
        setProgress(0, `Cleared ${outputs} rendered outputs.`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear outputs failed";
      setProgress(0, `Clear outputs failed: ${msg}`);
    } finally {
      setClearingOutputs(false);
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
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
    const label = videoName || "current clip";
    const confirmed = window.confirm(`Remove ${label} from your local library?`);
    if (!confirmed) return;
    setDeletingVideoId(videoId);
    try {
      const result = await deleteVideo(videoId);
      await refreshRecent();
      clearVideo();
      const outputs = result.deleted_outputs ?? 0;
      if (outputs > 0) {
        setOutputCount((prev) => (prev == null ? null : Math.max(0, prev - outputs)));
      }
      const outputPart = outputs <= 0
        ? ""
        : outputs === 1
          ? " Cleared 1 rendered output."
          : ` Cleared ${outputs} rendered outputs.`;
      setProgress(0, `Removed ${label} from local library.${outputPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setProgress(0, `Delete failed: ${msg}`);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleRenameCurrent = async () => {
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs) return;
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
        aria-keyshortcuts="Enter Space /"
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
                {normalizedRecentFilter
                  ? `Recent (${filteredRecent.length}/${recentVideos.length} · ${formatDuration(filteredRecentDuration)}/${formatDuration(totalRecentDuration)})`
                  : `Recent (${recentVideos.length} · ${formatDuration(totalRecentDuration)})`}
              </span>
              <span className="text-[9px] font-pixel text-text-muted/70 text-center">
                out:{outputCount ?? "?"}
              </span>
              <button
                onClick={() => void refreshRecent()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label="Refresh local clip library"
              >
                {refreshingRecent ? "[refreshing...]" : "[refresh]"}
              </button>
              <button
                onClick={() => void handleClearLibrary()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || recentVideos.length === 0}
                className="text-[9px] font-pixel text-magenta-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label="Clear all local clips"
              >
                {clearingLibrary ? "[clearing...]" : "[clear all]"}
              </button>
              <button
                onClick={() => void handleClearOutputs()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || outputCount === 0}
                className="text-[9px] font-pixel text-magenta-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label="Clear all rendered outputs"
              >
                {clearingOutputs ? "[clearing out...]" : "[clear outputs]"}
              </button>
              {filteredRecent.length > RECENT_PREVIEW_LIMIT && (
                <button
                  onClick={() => setShowAllRecent((prev) => !prev)}
                  disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs}
                  className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                  aria-label={showAllRecent ? "Show fewer recent clips" : "Show all recent clips"}
                >
                  {showAllRecent ? "[show less]" : "[show all]"}
                </button>
              )}
              <button
                onClick={() => {
                  setRecentSort((prev) => {
                    if (prev === "recent") return "name";
                    if (prev === "name") return "duration";
                    return "recent";
                  });
                }}
                disabled={recentVideos.length <= 1 || isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label={`Sort recent clips (currently ${recentSort})`}
              >
                [sort:{recentSort}]
              </button>
            </div>
            {recentVideos.length > 0 && (
              <div className="flex items-center justify-center gap-1">
                <input
                  ref={recentFilterInputRef}
                  value={recentFilter}
                  onChange={(e) => setRecentFilter(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      e.preventDefault();
                      setRecentFilter("");
                      e.currentTarget.blur();
                    }
                  }}
                  placeholder="filter clips"
                  aria-label="Filter recent clips by name"
                  className="w-[120px] bg-panel border border-cyan-500/20 rounded px-1.5 py-0.5 text-[9px] font-pixel text-cyan-100 placeholder:text-text-muted/60 focus:outline-none focus:border-cyan-300"
                />
                {recentFilter && (
                  <button
                    onClick={() => setRecentFilter("")}
                    className="text-[9px] font-pixel text-text-muted hover:text-white"
                    aria-label="Clear recent clip filter"
                  >
                    [x]
                  </button>
                )}
              </div>
            )}
            {visibleRecent.length > 0 ? (
              <div className="flex flex-wrap justify-center gap-1">
                {visibleRecent.map((item) => (
                  <div key={item.video_id} className="flex items-center gap-0.5">
                    <button
                      onClick={() => void handleLoadExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
                      className="retro-btn px-2 py-0.5 text-[10px] font-pixel tracking-wide max-w-[180px] truncate disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`${item.filename} · ${item.info.duration.toFixed(1)}s${item.cached ? " · cached analysis" : ""}`}
                    >
                      {item.cached ? "⚡ " : ""}
                      {shortName(item.filename)}
                    </button>
                    <button
                      onClick={() => void handleRenameExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
                      className="text-[10px] font-pixel px-1 py-0.5 border rounded border-cyan-400/40 text-cyan-200 hover:text-white hover:border-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`Rename ${item.filename}`}
                      aria-label={`Rename ${item.filename}`}
                    >
                      ✎
                    </button>
                    <button
                      onClick={() => void handleDeleteExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
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
              <span className="text-[10px] font-pixel text-text-muted/70 text-center">
                {recentVideos.length > 0 ? "no matching clips" : "no local clips"}
              </span>
            )}
            {hiddenRecentCount > 0 && !showAllRecent && (
              <span className="text-[9px] font-pixel text-text-muted/60 text-center">
                +{hiddenRecentCount} more clip{hiddenRecentCount === 1 ? "" : "s"}
              </span>
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
      <span className="text-[10px] font-pixel text-text-muted/70 whitespace-nowrap">
        out:{outputCount ?? "?"}
      </span>
      <Tooltip text="Clear current clip and return to upload/recent selector">
        <button
          onClick={handleClearVideo}
          disabled={isAnalyzing || isRendering || clearingOutputs}
          className="text-[11px] font-pixel text-text-muted hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [EJECT]
        </button>
      </Tooltip>
      <Tooltip text="Replace the current video with a new one">
        <button
          onClick={openPicker}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
          className="text-[11px] font-pixel text-neon-magenta hover:text-white retro-glow-magenta shrink-0 uppercase disabled:opacity-40 disabled:cursor-not-allowed"
        >
          [SWAP]
        </button>
      </Tooltip>
      <Tooltip text="Delete this clip from local library and clear the current session">
        <button
          onClick={() => void handleDeleteCurrent()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [DELETE]
        </button>
      </Tooltip>
      <Tooltip text="Rename current clip label in local library">
        <button
          onClick={() => void handleRenameCurrent()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
          className="text-[11px] font-pixel text-cyan-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [RENAME]
        </button>
      </Tooltip>
      <Tooltip text="Remove every clip from local library and reset to upload screen">
        <button
          onClick={() => void handleClearLibrary()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [CLEAR LIB]
        </button>
      </Tooltip>
      <Tooltip text="Delete all rendered outputs while keeping source clips">
        <button
          onClick={() => void handleClearOutputs()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || outputCount === 0}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          {clearingOutputs ? "[CLEARING OUT]" : "[CLEAR OUT]"}
        </button>
      </Tooltip>
    </div>
  );
}
