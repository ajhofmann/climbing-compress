"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { deleteAllOutputs, deleteAllVideos, deleteOutputsForVideo, deleteVideo, getLibraryStats, getVideoMeta, listVideos, renameVideo, uploadVideo, VideoListItem } from "@/lib/api";
import { Tooltip } from "@/components/tooltip";

const SUPPORTED_VIDEO_EXTS = [".mov", ".mp4", ".avi", ".mkv"] as const;
const RECENT_PREVIEW_LIMIT = 6;
const RECENT_PREF_KEY = "sendit.recentPrefs";
const RECENT_FILTER_TAGS = ["#cached", "#uncached", "#out", "#noout", "#short", "#long"] as const;

function formatBytesShort(bytes: number | null) {
  if (bytes == null || !Number.isFinite(bytes)) return "?";
  const safe = Math.max(0, Math.round(bytes));
  if (safe < 1024) return `${safe}b`;
  if (safe < 1024 * 1024) return `${(safe / 1024).toFixed(safe < 10 * 1024 ? 1 : 0)}k`;
  if (safe < 1024 * 1024 * 1024) return `${(safe / (1024 * 1024)).toFixed(safe < 10 * 1024 * 1024 ? 1 : 0)}m`;
  return `${(safe / (1024 * 1024 * 1024)).toFixed(safe < 10 * 1024 * 1024 * 1024 ? 1 : 0)}g`;
}

function formatBytesVerbose(bytes: number | null) {
  if (bytes == null || !Number.isFinite(bytes)) return "unknown size";
  const safe = Math.max(0, bytes);
  if (safe < 1024) return `${safe.toFixed(0)} B`;
  if (safe < 1024 * 1024) return `${(safe / 1024).toFixed(1)} KB`;
  if (safe < 1024 * 1024 * 1024) return `${(safe / (1024 * 1024)).toFixed(1)} MB`;
  return `${(safe / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function VideoUpload() {
  const videoId = useStore((state) => state.videoId);
  const outputId = useStore((state) => state.outputId);
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
  const [clearingFilteredOutputs, setClearingFilteredOutputs] = useState(false);
  const [pruningFiltered, setPruningFiltered] = useState(false);
  const [clipBytes, setClipBytes] = useState<number | null>(null);
  const [currentSourceBytes, setCurrentSourceBytes] = useState<number | null>(null);
  const [outputCount, setOutputCount] = useState<number | null>(null);
  const [outputBytes, setOutputBytes] = useState<number | null>(null);
  const [clipOutputCount, setClipOutputCount] = useState<number | null>(null);
  const [clipOutputBytes, setClipOutputBytes] = useState<number | null>(null);
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [recentFilter, setRecentFilter] = useState("");
  const [recentFilterFocused, setRecentFilterFocused] = useState(false);
  const [recentCursorIdx, setRecentCursorIdx] = useState(-1);
  const [recentSort, setRecentSort] = useState<"recent" | "name" | "duration" | "outputs" | "size">("recent");
  const [recentSortReversed, setRecentSortReversed] = useState(false);
  const [recentOutputScope, setRecentOutputScope] = useState<"all" | "with" | "none">("all");
  const [recentCacheScope, setRecentCacheScope] = useState<"all" | "cached" | "uncached">("all");
  const recentFilterInputRef = useRef<HTMLInputElement>(null);

  const cycleRecentSort = useCallback(() => {
    setRecentSort((prev) => {
      if (prev === "recent") return "name";
      if (prev === "name") return "duration";
      if (prev === "duration") return "outputs";
      if (prev === "outputs") return "size";
      return "recent";
    });
  }, []);

  const resetRecentView = useCallback(() => {
    setRecentFilter("");
    setRecentOutputScope("all");
    setRecentCacheScope("all");
  }, []);
  const resetRecentViewAll = useCallback(() => {
    resetRecentView();
    setRecentSort("recent");
    setRecentSortReversed(false);
    setShowAllRecent(false);
    setShowShortcutHelp(false);
    setRecentCursorIdx(-1);
  }, [resetRecentView]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(RECENT_PREF_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { sort?: string; showAll?: boolean; outputScope?: string; cacheScope?: string; filter?: string; shortcutHelp?: boolean; sortReverse?: boolean };
      if (parsed.sort === "recent" || parsed.sort === "name" || parsed.sort === "duration" || parsed.sort === "outputs" || parsed.sort === "size") {
        setRecentSort(parsed.sort);
      }
      if (typeof parsed.sortReverse === "boolean") {
        setRecentSortReversed(parsed.sortReverse);
      }
      if (typeof parsed.showAll === "boolean") {
        setShowAllRecent(parsed.showAll);
      }
      if (parsed.outputScope === "all" || parsed.outputScope === "with" || parsed.outputScope === "none") {
        setRecentOutputScope(parsed.outputScope);
      }
      if (parsed.cacheScope === "all" || parsed.cacheScope === "cached" || parsed.cacheScope === "uncached") {
        setRecentCacheScope(parsed.cacheScope);
      }
      if (typeof parsed.filter === "string") {
        setRecentFilter(parsed.filter.slice(0, 120));
      }
      if (typeof parsed.shortcutHelp === "boolean") {
        setShowShortcutHelp(parsed.shortcutHelp);
      }
    } catch {
      // ignore malformed local preferences
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(RECENT_PREF_KEY, JSON.stringify({
        sort: recentSort,
        sortReverse: recentSortReversed,
        showAll: showAllRecent,
        outputScope: recentOutputScope,
        cacheScope: recentCacheScope,
        filter: recentFilter,
        shortcutHelp: showShortcutHelp,
      }));
    } catch {
      // ignore storage write failures
    }
  }, [recentSort, recentSortReversed, showAllRecent, recentOutputScope, recentCacheScope, recentFilter, showShortcutHelp]);

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

  const applyRecent = useCallback((items: VideoListItem[]) => {
    setRecentVideos(items);
    setShowAllRecent((prev) => (items.length > RECENT_PREVIEW_LIMIT ? prev : false));
  }, []);

  const normalizedRecentFilter = recentFilter.trim().toLowerCase();
  const recentFilterTerms = useMemo(
    () => normalizedRecentFilter.split(/\s+/).filter(Boolean),
    [normalizedRecentFilter],
  );
  const parsedRecentFilterTerms = useMemo(
    () => recentFilterTerms.map((raw, idx) => {
      const isExclude = raw.startsWith("-") && raw.length > 1;
      const term = isExclude ? raw.slice(1) : raw;
      return { idx, raw, term, isExclude };
    }).filter((item) => item.term.length > 0),
    [recentFilterTerms],
  );
  const includeRecentFilterTerms = useMemo(
    () => parsedRecentFilterTerms.filter((item) => !item.isExclude).map((item) => item.term),
    [parsedRecentFilterTerms],
  );
  const excludeRecentFilterTerms = useMemo(
    () => parsedRecentFilterTerms.filter((item) => item.isExclude).map((item) => item.term),
    [parsedRecentFilterTerms],
  );
  const matchesRecentFilterTerm = useCallback((item: VideoListItem, term: string) => {
    if (term.startsWith("#")) {
      const tag = term.slice(1);
      if (tag === "cached") return item.cached;
      if (tag === "uncached") return !item.cached;
      if (tag === "out") return item.output_count > 0;
      if (tag === "noout") return item.output_count <= 0;
      if (tag === "short") return item.info.duration <= 5;
      if (tag === "long") return item.info.duration > 5;
    }
    return item.filename.toLowerCase().includes(term);
  }, []);
  const nameFilteredRecent = useMemo(() => (
    recentFilterTerms.length > 0
      ? recentVideos.filter((item) => {
        return includeRecentFilterTerms.every((term) => matchesRecentFilterTerm(item, term))
          && excludeRecentFilterTerms.every((term) => !matchesRecentFilterTerm(item, term));
      })
      : recentVideos
  ), [recentVideos, recentFilterTerms.length, includeRecentFilterTerms, excludeRecentFilterTerms, matchesRecentFilterTerm]);
  const removeRecentFilterTerm = useCallback((termIndex: number) => {
    const sourceTerms = recentFilter.trim().split(/\s+/).filter(Boolean);
    if (termIndex < 0 || termIndex >= sourceTerms.length) return;
    sourceTerms.splice(termIndex, 1);
    setRecentFilter(sourceTerms.join(" "));
    setRecentCursorIdx(-1);
    recentFilterInputRef.current?.focus();
  }, [recentFilter]);
  const popRecentFilterTerm = useCallback(() => {
    const sourceTerms = recentFilter.trim().split(/\s+/).filter(Boolean);
    if (sourceTerms.length <= 0) return;
    sourceTerms.pop();
    setRecentFilter(sourceTerms.join(" "));
    setRecentCursorIdx(-1);
    recentFilterInputRef.current?.focus();
  }, [recentFilter]);
  const recentTagSuggestions = useMemo(() => {
    if (!recentFilterFocused || recentFilter.endsWith(" ")) return [] as string[];
    const sourceTerms = recentFilter.trim().split(/\s+/).filter(Boolean);
    const tail = sourceTerms[sourceTerms.length - 1]?.toLowerCase() ?? "";
    const isExcludeTag = tail.startsWith("-#");
    const isIncludeTag = tail.startsWith("#");
    if (!isExcludeTag && !isIncludeTag) return [] as string[];
    const normalizedTail = isExcludeTag ? tail.slice(1) : tail;
    const base = RECENT_FILTER_TAGS.filter((tag) => tag.startsWith(normalizedTail));
    return isExcludeTag ? base.map((tag) => `-${tag}`) : [...base];
  }, [recentFilter, recentFilterFocused]);
  const applyRecentTagSuggestion = useCallback((suggestion: string) => {
    const sourceTerms = recentFilter.trim().split(/\s+/).filter(Boolean);
    const hasTagTail = sourceTerms.length > 0 && /^-?#/.test(sourceTerms[sourceTerms.length - 1]);
    if (hasTagTail) {
      sourceTerms[sourceTerms.length - 1] = suggestion;
    } else {
      sourceTerms.push(suggestion);
    }
    setRecentFilter(`${sourceTerms.join(" ")} `);
    setRecentCursorIdx(-1);
    recentFilterInputRef.current?.focus();
  }, [recentFilter]);

  const outputScopedRecent = useMemo(() => {
    if (recentOutputScope === "all") return nameFilteredRecent;
    if (recentOutputScope === "with") return nameFilteredRecent.filter((item) => item.output_count > 0);
    return nameFilteredRecent.filter((item) => item.output_count <= 0);
  }, [nameFilteredRecent, recentOutputScope]);

  const cacheScopedRecent = useMemo(() => {
    if (recentCacheScope === "all") return nameFilteredRecent;
    if (recentCacheScope === "cached") return nameFilteredRecent.filter((item) => item.cached);
    return nameFilteredRecent.filter((item) => !item.cached);
  }, [nameFilteredRecent, recentCacheScope]);

  const filteredRecent = useMemo(() => {
    if (recentCacheScope === "all") return outputScopedRecent;
    if (recentCacheScope === "cached") return outputScopedRecent.filter((item) => item.cached);
    return outputScopedRecent.filter((item) => !item.cached);
  }, [outputScopedRecent, recentCacheScope]);

  const sortedRecentBase = useMemo(() => (
    recentSort === "recent"
      ? filteredRecent
      : [...filteredRecent].sort((a, b) => {
        if (recentSort === "name") return a.filename.localeCompare(b.filename, undefined, { sensitivity: "base" });
        if (recentSort === "outputs") {
          const byOutputs = b.output_count - a.output_count;
          if (byOutputs !== 0) return byOutputs;
          return a.filename.localeCompare(b.filename, undefined, { sensitivity: "base" });
        }
        if (recentSort === "size") {
          const bySourceBytes = b.source_bytes - a.source_bytes;
          if (bySourceBytes !== 0) return bySourceBytes;
          const byOutputBytes = b.output_bytes - a.output_bytes;
          if (byOutputBytes !== 0) return byOutputBytes;
          return a.filename.localeCompare(b.filename, undefined, { sensitivity: "base" });
        }
        const byDuration = b.info.duration - a.info.duration;
        if (Math.abs(byDuration) > 1e-6) return byDuration;
        return a.filename.localeCompare(b.filename, undefined, { sensitivity: "base" });
      })
  ), [filteredRecent, recentSort]);
  const sortedRecent = useMemo(() => (
    recentSortReversed ? [...sortedRecentBase].reverse() : sortedRecentBase
  ), [sortedRecentBase, recentSortReversed]);

  const visibleRecent = useMemo(() => (
    showAllRecent
      ? sortedRecent
      : sortedRecent.slice(0, RECENT_PREVIEW_LIMIT)
  ), [showAllRecent, sortedRecent]);
  useEffect(() => {
    setRecentCursorIdx(-1);
  }, [normalizedRecentFilter, recentOutputScope, recentCacheScope, recentSort, recentSortReversed, showAllRecent]);
  useEffect(() => {
    setRecentCursorIdx((prev) => {
      if (visibleRecent.length <= 0) return -1;
      if (prev < 0) return prev;
      return Math.min(prev, visibleRecent.length - 1);
    });
  }, [visibleRecent.length]);

  const hiddenRecentCount = Math.max(0, sortedRecent.length - visibleRecent.length);
  const outputScopeCount = useMemo(() => {
    if (recentOutputScope === "all") return cacheScopedRecent.length;
    if (recentOutputScope === "with") return cacheScopedRecent.filter((item) => item.output_count > 0).length;
    return cacheScopedRecent.filter((item) => item.output_count <= 0).length;
  }, [cacheScopedRecent, recentOutputScope]);
  const cacheScopeCount = useMemo(() => {
    if (recentCacheScope === "all") return outputScopedRecent.length;
    if (recentCacheScope === "cached") return outputScopedRecent.filter((item) => item.cached).length;
    return outputScopedRecent.filter((item) => !item.cached).length;
  }, [outputScopedRecent, recentCacheScope]);
  const totalRecentDuration = useMemo(
    () => recentVideos.reduce((sum, item) => sum + item.info.duration, 0),
    [recentVideos],
  );
  const filteredRecentDuration = useMemo(
    () => filteredRecent.reduce((sum, item) => sum + item.info.duration, 0),
    [filteredRecent],
  );
  const filteredSourceBytes = useMemo(
    () => filteredRecent.reduce((sum, item) => sum + item.source_bytes, 0),
    [filteredRecent],
  );
  const filteredOutputCount = useMemo(
    () => filteredRecent.reduce((sum, item) => sum + item.output_count, 0),
    [filteredRecent],
  );
  const filteredClipsWithOutputs = useMemo(
    () => filteredRecent.reduce((count, item) => count + (item.output_count > 0 ? 1 : 0), 0),
    [filteredRecent],
  );
  const filteredOutputBytes = useMemo(
    () => filteredRecent.reduce((sum, item) => sum + item.output_bytes, 0),
    [filteredRecent],
  );
  const hasActiveRecentSubset = normalizedRecentFilter.length > 0 || recentOutputScope !== "all" || recentCacheScope !== "all";
  const hasAnyRecentCustomization = hasActiveRecentSubset || recentSort !== "recent" || recentSortReversed || showAllRecent || showShortcutHelp;

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
          setClipBytes(statsRes.value.clip_bytes);
          setOutputCount(statsRes.value.outputs);
          setOutputBytes(statsRes.value.output_bytes);
        } else {
          setClipBytes(null);
          setOutputCount(null);
          setOutputBytes(null);
        }
        setClipOutputCount(null);
        setClipOutputBytes(null);
        setRecentFetchDone(true);
      })
    return () => {
      cancelled = true;
    };
  }, [videoId, applyRecent]);

  useEffect(() => {
    if (!videoId) {
      setCurrentSourceBytes(null);
      setClipOutputCount(null);
      setClipOutputBytes(null);
      return;
    }
    let cancelled = false;
    void getLibraryStats(videoId)
      .then((stats) => {
        if (cancelled) return;
        setClipBytes(stats.clip_bytes);
        setOutputCount(stats.outputs);
        setOutputBytes(stats.output_bytes);
        setClipOutputCount(typeof stats.clip_outputs === "number" ? stats.clip_outputs : null);
        setClipOutputBytes(typeof stats.clip_output_bytes === "number" ? stats.clip_output_bytes : null);
      })
      .catch(() => {
        if (cancelled) return;
        setClipOutputCount(null);
        setClipOutputBytes(null);
      });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  useEffect(() => {
    if (!outputId) return;
    let cancelled = false;
    void getLibraryStats(videoId ?? undefined)
      .then((stats) => {
        if (cancelled) return;
        setClipBytes(stats.clip_bytes);
        setOutputCount(stats.outputs);
        setOutputBytes(stats.output_bytes);
        if (videoId) {
          setClipOutputCount(typeof stats.clip_outputs === "number" ? stats.clip_outputs : null);
          setClipOutputBytes(typeof stats.clip_output_bytes === "number" ? stats.clip_output_bytes : null);
        }
      })
      .catch(() => {
        // best-effort refresh only
        if (cancelled) return;
        if (videoId) setClipOutputBytes(null);
      });
    return () => {
      cancelled = true;
    };
  }, [outputId, videoId]);

  const refreshRecent = useCallback(async () => {
    setRefreshingRecent(true);
    try {
      const [videosRes, statsRes] = await Promise.allSettled([listVideos(), getLibraryStats()]);
      if (videosRes.status === "fulfilled") {
        applyRecent(videosRes.value);
      } else {
        applyRecent([]);
      }
      if (statsRes.status === "fulfilled") {
        setClipBytes(statsRes.value.clip_bytes);
        setOutputCount(statsRes.value.outputs);
        setOutputBytes(statsRes.value.output_bytes);
      } else {
        setClipBytes(null);
        setOutputCount(null);
        setOutputBytes(null);
      }
      setClipOutputCount(null);
      setClipOutputBytes(null);
    } catch {
      applyRecent([]);
      setClipBytes(null);
      setOutputCount(null);
      setOutputBytes(null);
      setClipOutputCount(null);
      setClipOutputBytes(null);
    } finally {
      setRecentFetchDone(true);
      setRefreshingRecent(false);
    }
  }, [applyRecent]);

  const handleLoadExisting = useCallback(async (item: VideoListItem) => {
    if (deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    setProgress(0.05, `Loading ${item.filename}...`);
    try {
      const meta = await getVideoMeta(item.video_id);
      setVideo(meta.video_id, meta.info, meta.thumbnails, meta.filename);
      setCurrentSourceBytes(meta.source_bytes ?? item.source_bytes);
      setClipOutputCount(meta.output_count ?? item.output_count);
      setClipOutputBytes(meta.output_bytes ?? item.output_bytes);
      setProgress(0, `Loaded ${meta.filename}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Load failed";
      setProgress(0, `Load failed: ${msg}`);
    }
  }, [
    deletingVideoId,
    renamingVideoId,
    clearingLibrary,
    clearingOutputs,
    pruningFiltered,
    setProgress,
    setVideo,
  ]);

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
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || target?.isContentEditable) return;
      if (e.key === "?" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setShowShortcutHelp((prev) => !prev);
        return;
      }
      if (/^[0-9]$/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
        const idx = e.key === "0" ? 9 : Number(e.key) - 1;
        if (idx < 0 || idx >= visibleRecent.length) return;
        e.preventDefault();
        void handleLoadExisting(visibleRecent[idx]);
        return;
      }
      if (e.key.toLowerCase() === "o" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setRecentOutputScope((prev) => {
          if (prev === "all") return "with";
          if (prev === "with") return "none";
          return "all";
        });
        return;
      }
      if (e.key.toLowerCase() === "c" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setRecentCacheScope((prev) => {
          if (prev === "all") return "cached";
          if (prev === "cached") return "uncached";
          return "all";
        });
        return;
      }
      if (e.key.toLowerCase() === "s" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (recentVideos.length <= 1) return;
        e.preventDefault();
        cycleRecentSort();
        return;
      }
      if (e.key.toLowerCase() === "d" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (recentVideos.length <= 1) return;
        e.preventDefault();
        setRecentSortReversed((prev) => !prev);
        return;
      }
      if (e.key.toLowerCase() === "r" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered) return;
        e.preventDefault();
        void refreshRecent();
        return;
      }
      if (e.key.toLowerCase() === "v" && e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (!hasAnyRecentCustomization) return;
        e.preventDefault();
        resetRecentViewAll();
        return;
      }
      if (e.key.toLowerCase() === "v" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (!hasActiveRecentSubset) return;
        e.preventDefault();
        resetRecentView();
        return;
      }
      if (e.key.toLowerCase() === "a" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (filteredRecent.length <= RECENT_PREVIEW_LIMIT) return;
        e.preventDefault();
        setShowAllRecent((prev) => !prev);
        return;
      }
      if (e.key !== "/") return;
      e.preventDefault();
      recentFilterInputRef.current?.focus();
    };
    window.addEventListener("keydown", onGlobalKeyDown, true);
    return () => window.removeEventListener("keydown", onGlobalKeyDown, true);
  }, [
    videoId,
    recentFetchDone,
    recentFilter,
    isAnalyzing,
    isRendering,
    deletingVideoId,
    renamingVideoId,
    refreshingRecent,
    clearingLibrary,
    clearingOutputs,
    pruningFiltered,
    hasActiveRecentSubset,
    hasAnyRecentCustomization,
    recentCacheScope,
    recentVideos.length,
    filteredRecent.length,
    visibleRecent,
    cycleRecentSort,
    resetRecentView,
    resetRecentViewAll,
    refreshRecent,
    handleLoadExisting,
  ]);

  const handleFile = async (file: File) => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const ext = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase()}` : "";
    if (!SUPPORTED_VIDEO_EXTS.includes(ext as typeof SUPPORTED_VIDEO_EXTS[number])) {
      setProgress(0, `Unsupported file type (${ext || "unknown"}). Use ${SUPPORTED_VIDEO_EXTS.join(", ")}`);
      return;
    }
    setProgress(0.05, "Uploading video...");
    try {
      const data = await uploadVideo(file);
      setVideo(data.video_id, data.info, data.thumbnails, data.filename);
      setCurrentSourceBytes(data.source_bytes ?? null);
      setClipOutputCount(data.output_count ?? 0);
      setClipOutputBytes(data.output_bytes ?? 0);
      const cacheHint = data.cached ? " (analysis cached)" : "";
      const label = data.filename || file.name;
      const status = data.reused ? `Loaded existing clip ${label}` : `Uploaded ${label}`;
      setProgress(0, `${status}${cacheHint}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setProgress(0, `Upload failed: ${msg}`);
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
    if (deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    await runRename(item.video_id, item.filename);
  };

  const handleDeleteExisting = async (item: VideoListItem) => {
    if (deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const confirmed = window.confirm(`Remove ${item.filename} from your local library?`);
    if (!confirmed) return;
    setDeletingVideoId(item.video_id);
    try {
      const result = await deleteVideo(item.video_id);
      await refreshRecent();
      const outputs = result.deleted_outputs ?? 0;
      const clipBytesFreed = result.deleted_bytes ?? 0;
      const outputBytesFreed = result.deleted_output_bytes ?? 0;
      const clipPart = clipBytesFreed > 0 ? ` Freed ${formatBytesVerbose(clipBytesFreed)} source media.` : "";
      const outputPart = outputs <= 0
        ? ""
        : outputs === 1
          ? ` Cleared 1 rendered output (${formatBytesVerbose(outputBytesFreed)}).`
          : ` Cleared ${outputs} rendered outputs (${formatBytesVerbose(outputBytesFreed)}).`;
      setProgress(0, `Removed ${item.filename}.${clipPart}${outputPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setProgress(0, `Delete failed: ${msg}`);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleClearOutputsForExisting = async (item: VideoListItem) => {
    if (item.output_count <= 0 || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const confirmed = window.confirm(`Remove rendered outputs for ${item.filename} only?`);
    if (!confirmed) return;
    setClearingOutputs(true);
    try {
      const result = await deleteOutputsForVideo(item.video_id);
      const outputs = result.deleted_outputs ?? 0;
      const outputBytesRemoved = result.deleted_output_bytes ?? 0;
      if (videoId === item.video_id) setClipOutputCount(0);
      if (videoId === item.video_id) setClipOutputBytes(0);
      setRecentVideos((prev) => prev.map((row) => (
        row.video_id === item.video_id
          ? { ...row, output_count: 0 }
          : row
      )));
      try {
        const stats = await getLibraryStats();
        setClipBytes(stats.clip_bytes);
        setOutputCount(stats.outputs);
        setOutputBytes(stats.output_bytes);
      } catch {
        // keep local optimistic counters if stats refresh fails
        setOutputCount((prev) => {
          if (prev == null) return null;
          return Math.max(0, prev - outputs);
        });
        setOutputBytes((prev) => {
          if (prev == null) return null;
          return Math.max(0, prev - outputBytesRemoved);
        });
      }
      const freedPart = outputBytesRemoved > 0 ? ` Freed ${formatBytesVerbose(outputBytesRemoved)}.` : "";
      if (outputs <= 0) {
        setProgress(0, `No rendered outputs found for ${item.filename}.`);
      } else if (outputs === 1) {
        setProgress(0, `Cleared 1 rendered output for ${item.filename}.${freedPart}`);
      } else {
        setProgress(0, `Cleared ${outputs} rendered outputs for ${item.filename}.${freedPart}`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear outputs failed";
      setProgress(0, `Clear outputs failed: ${msg}`);
    } finally {
      setClearingOutputs(false);
    }
  };

  const handleClearLibrary = async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const clipSummary = `${recentVideos.length} local clip${recentVideos.length === 1 ? "" : "s"}, ${formatBytesVerbose(clipBytes)}`;
    const outputSummary = `${outputCount ?? 0} rendered output${outputCount === 1 ? "" : "s"}, ${formatBytesVerbose(outputBytes)}`;
    const confirmed = window.confirm(`Remove all local clips from this library? (${clipSummary}; ${outputSummary})`);
    if (!confirmed) return;
    const shouldClearCurrent = Boolean(videoId);
    setClearingLibrary(true);
    try {
      const result = await deleteAllVideos();
      setRecentVideos([]);
      setShowAllRecent(false);
      setRecentFetchDone(true);
      setClipBytes(0);
      setCurrentSourceBytes(0);
      setOutputCount(0);
      setOutputBytes(0);
      setClipOutputCount(0);
      setClipOutputBytes(0);
      if (shouldClearCurrent) clearVideo();
      const count = result.deleted ?? 0;
      const outputs = result.deleted_outputs ?? 0;
      const clipBytesFreed = result.deleted_bytes ?? 0;
      const outputBytesFreed = result.deleted_output_bytes ?? 0;
      const clipPart = count <= 0
        ? "Local library already empty."
        : count === 1
          ? "Removed 1 local clip."
          : `Removed ${count} local clips.`;
      const clipBytesPart = clipBytesFreed > 0
        ? ` Freed ${formatBytesVerbose(clipBytesFreed)} source media.`
        : "";
      const outputPart = outputs <= 0
        ? ""
        : outputs === 1
          ? ` Cleared 1 rendered output (${formatBytesVerbose(outputBytesFreed)}).`
          : ` Cleared ${outputs} rendered outputs (${formatBytesVerbose(outputBytesFreed)}).`;
      setProgress(0, `${clipPart}${clipBytesPart}${outputPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear failed";
      setProgress(0, `Clear failed: ${msg}`);
    } finally {
      setClearingLibrary(false);
    }
  };

  const handleClearFiltered = async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered) return;
    if (!hasActiveRecentSubset) {
      setProgress(0, "No filtered subset is active. Use [clear all] to wipe the full library.");
      return;
    }
    if (filteredRecent.length <= 0) {
      setProgress(0, "No filtered clips to clear.");
      return;
    }
    const clipSummary = `${filteredRecent.length} filtered clip${filteredRecent.length === 1 ? "" : "s"}, ${formatBytesVerbose(filteredSourceBytes)}`;
    let confirmOutputCount = filteredOutputCount;
    let confirmOutputBytes = filteredOutputBytes;
    try {
      const clipStats = await Promise.all(filteredRecent.map((item) => getLibraryStats(item.video_id)));
      confirmOutputCount = clipStats.reduce((sum, stats) => sum + (stats.clip_outputs ?? 0), 0);
      confirmOutputBytes = clipStats.reduce((sum, stats) => sum + (stats.clip_output_bytes ?? 0), 0);
    } catch {
      // Fall back to local aggregate if live stats lookup fails.
    }
    const outputSummary = `${confirmOutputCount} rendered output${confirmOutputCount === 1 ? "" : "s"}, ${formatBytesVerbose(confirmOutputBytes)}`;
    const confirmed = window.confirm(`Remove filtered clips from local library? (${clipSummary}; ${outputSummary})`);
    if (!confirmed) return;
    setPruningFiltered(true);
    try {
      let deleted = 0;
      let deletedOutputs = 0;
      let deletedBytes = 0;
      let deletedOutputBytes = 0;
      let failed = 0;
      const targets = [...filteredRecent];
      for (const item of targets) {
        try {
          const result = await deleteVideo(item.video_id);
          if (result.deleted) deleted += 1;
          deletedOutputs += result.deleted_outputs ?? 0;
          deletedBytes += result.deleted_bytes ?? 0;
          deletedOutputBytes += result.deleted_output_bytes ?? 0;
        } catch {
          failed += 1;
        }
      }
      await refreshRecent();
      const clipPart = deleted <= 0
        ? "No filtered clips were removed."
        : deleted === 1
          ? "Removed 1 filtered clip."
          : `Removed ${deleted} filtered clips.`;
      const clipBytesPart = deletedBytes > 0 ? ` Freed ${formatBytesVerbose(deletedBytes)} source media.` : "";
      const outputPart = deletedOutputs <= 0
        ? ""
        : deletedOutputs === 1
          ? ` Cleared 1 rendered output (${formatBytesVerbose(deletedOutputBytes)}).`
          : ` Cleared ${deletedOutputs} rendered outputs (${formatBytesVerbose(deletedOutputBytes)}).`;
      const failPart = failed <= 0
        ? ""
        : failed === 1
          ? " 1 clip failed to delete."
          : ` ${failed} clips failed to delete.`;
      setProgress(0, `${clipPart}${clipBytesPart}${outputPart}${failPart}`);
    } finally {
      setPruningFiltered(false);
    }
  };

  const handleClearFilteredOutputs = useCallback(async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered) return;
    if (!hasActiveRecentSubset) {
      setProgress(0, "No filtered clip subset is active.");
      return;
    }
    if (filteredRecent.length <= 0) {
      setProgress(0, "No filtered clips to clear outputs for.");
      return;
    }

    const liveOutputStats = await Promise.all(filteredRecent.map(async (item) => {
      try {
        const stats = await getLibraryStats(item.video_id);
        return {
          videoId: item.video_id,
          outputs: Math.max(0, stats.clip_outputs ?? item.output_count),
          bytes: Math.max(0, stats.clip_output_bytes ?? item.output_bytes),
        };
      } catch {
        return {
          videoId: item.video_id,
          outputs: Math.max(0, item.output_count),
          bytes: Math.max(0, item.output_bytes),
        };
      }
    }));

    const confirmOutputCount = liveOutputStats.reduce((sum, item) => sum + item.outputs, 0);
    if (confirmOutputCount <= 0) {
      setProgress(0, "No rendered outputs matched current filters.");
      return;
    }
    const confirmOutputBytes = liveOutputStats.reduce((sum, item) => sum + item.bytes, 0);
    const confirmClipCount = liveOutputStats.reduce((count, item) => count + (item.outputs > 0 ? 1 : 0), 0);
    const confirmText = `Remove filtered rendered outputs? (${confirmOutputCount} rendered output${confirmOutputCount === 1 ? "" : "s"} across ${confirmClipCount}/${filteredRecent.length} clips, ${formatBytesVerbose(confirmOutputBytes)})`;
    if (!window.confirm(confirmText)) return;

    setClearingOutputs(true);
    setClearingFilteredOutputs(true);
    try {
      let clearedOutputs = 0;
      let clearedBytes = 0;
      let clearedClips = 0;
      let failed = 0;
      const targets = liveOutputStats.filter((item) => item.outputs > 0);
      for (const item of targets) {
        try {
          const result = await deleteOutputsForVideo(item.videoId);
          const removed = result.deleted_outputs ?? 0;
          if (removed > 0) clearedClips += 1;
          clearedOutputs += removed;
          clearedBytes += result.deleted_output_bytes ?? 0;
        } catch {
          failed += 1;
        }
      }
      await refreshRecent();
      if (clearedOutputs <= 0) {
        const failPart = failed <= 0
          ? ""
          : failed === 1
            ? " 1 clip failed to clear."
            : ` ${failed} clips failed to clear.`;
        setProgress(0, `No rendered outputs were cleared.${failPart}`);
        return;
      }
      const outputPart = clearedOutputs === 1
        ? "Cleared 1 rendered output"
        : `Cleared ${clearedOutputs} rendered outputs`;
      const clipPart = ` across ${clearedClips} clip${clearedClips === 1 ? "" : "s"}.`;
      const bytesPart = clearedBytes > 0 ? ` Freed ${formatBytesVerbose(clearedBytes)}.` : "";
      const failPart = failed <= 0
        ? ""
        : failed === 1
          ? " 1 clip failed to clear."
          : ` ${failed} clips failed to clear.`;
      setProgress(0, `${outputPart}${clipPart}${bytesPart}${failPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear outputs failed";
      setProgress(0, `Clear outputs failed: ${msg}`);
    } finally {
      setClearingFilteredOutputs(false);
      setClearingOutputs(false);
    }
  }, [
    isAnalyzing,
    isRendering,
    deletingVideoId,
    renamingVideoId,
    refreshingRecent,
    clearingLibrary,
    clearingOutputs,
    pruningFiltered,
    hasActiveRecentSubset,
    filteredRecent,
    setProgress,
    refreshRecent,
  ]);

  const handleClearAllOutputs = useCallback(async () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const outputLabel = outputCount && outputCount > 0
      ? `${outputCount} rendered output${outputCount === 1 ? "" : "s"}, ${formatBytesVerbose(outputBytes)}`
      : "all rendered outputs";
    const confirmed = window.confirm(`Remove ${outputLabel}? (keeps source clips)`);
    if (!confirmed) return;
    setClearingOutputs(true);
    try {
      const result = await deleteAllOutputs();
      const outputs = result.deleted_outputs ?? 0;
      const bytesRemoved = result.deleted_output_bytes ?? 0;
      setOutputCount(0);
      setOutputBytes(0);
      if (videoId) setClipOutputCount(0);
      if (videoId) setClipOutputBytes(0);
      setRecentVideos((prev) => prev.map((item) => ({ ...item, output_count: 0 })));
      const freedPart = bytesRemoved > 0
        ? ` Freed ${formatBytesVerbose(bytesRemoved)}.`
        : "";
      if (outputs <= 0) {
        setProgress(0, "No rendered outputs to clear.");
      } else if (outputs === 1) {
        setProgress(0, `Cleared 1 rendered output.${freedPart}`);
      } else {
        setProgress(0, `Cleared ${outputs} rendered outputs.${freedPart}`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear outputs failed";
      setProgress(0, `Clear outputs failed: ${msg}`);
    } finally {
      setClearingOutputs(false);
    }
  }, [
    isAnalyzing,
    isRendering,
    deletingVideoId,
    renamingVideoId,
    clearingLibrary,
    clearingOutputs,
    pruningFiltered,
    outputCount,
    outputBytes,
    videoId,
    setProgress,
  ]);

  const handleClearCurrentOutputs = useCallback(async () => {
    if (!videoId || !clipOutputCount || clipOutputCount <= 0 || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const clipSummary = `${clipOutputCount} rendered output${clipOutputCount === 1 ? "" : "s"}, ${formatBytesVerbose(clipOutputBytes)}`;
    const confirmed = window.confirm(`Remove rendered outputs for this clip only? (${clipSummary})`);
    if (!confirmed) return;
    setClearingOutputs(true);
    try {
      const result = await deleteOutputsForVideo(videoId);
      const outputs = result.deleted_outputs ?? 0;
      const outputBytesRemoved = result.deleted_output_bytes ?? 0;
      setClipOutputCount(0);
      setClipOutputBytes(0);
      setRecentVideos((prev) => prev.map((item) => (
        item.video_id === videoId
          ? { ...item, output_count: 0 }
          : item
      )));
      try {
        const stats = await getLibraryStats(videoId);
        setClipBytes(stats.clip_bytes);
        setOutputCount(stats.outputs);
        setOutputBytes(stats.output_bytes);
        setClipOutputCount(typeof stats.clip_outputs === "number" ? stats.clip_outputs : 0);
        setClipOutputBytes(typeof stats.clip_output_bytes === "number" ? stats.clip_output_bytes : 0);
      } catch {
        setOutputCount((prev) => {
          if (prev == null) return null;
          return Math.max(0, prev - outputs);
        });
        setOutputBytes((prev) => {
          if (prev == null) return null;
          return Math.max(0, prev - outputBytesRemoved);
        });
      }
      const freedPart = outputBytesRemoved > 0
        ? ` Freed ${formatBytesVerbose(outputBytesRemoved)}.`
        : "";
      if (outputs <= 0) {
        setProgress(0, "No rendered outputs found for current clip.");
      } else if (outputs === 1) {
        setProgress(0, `Cleared 1 rendered output for current clip.${freedPart}`);
      } else {
        setProgress(0, `Cleared ${outputs} rendered outputs for current clip.${freedPart}`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Clear outputs failed";
      setProgress(0, `Clear outputs failed: ${msg}`);
    } finally {
      setClearingOutputs(false);
    }
  }, [
    videoId,
    clipOutputCount,
    isAnalyzing,
    isRendering,
    deletingVideoId,
    renamingVideoId,
    clearingLibrary,
    clearingOutputs,
    pruningFiltered,
    clipOutputBytes,
    setProgress,
  ]);

  const openPicker = () => {
    if (isAnalyzing || isRendering || deletingVideoId || renamingVideoId || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = SUPPORTED_VIDEO_EXTS.join(",");
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) handleFile(file);
    };
    input.click();
  };

  const handleClearVideo = useCallback(() => {
    if (isAnalyzing || isRendering || clearingOutputs || pruningFiltered) return;
    setCurrentSourceBytes(null);
    clearVideo();
    setProgress(0, "Clip cleared. Pick another video or use Recent.");
  }, [
    isAnalyzing,
    isRendering,
    clearingOutputs,
    pruningFiltered,
    clearVideo,
    setProgress,
  ]);

  const handleDeleteCurrent = async () => {
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    const label = videoName || "current clip";
    const confirmed = window.confirm(`Remove ${label} from your local library?`);
    if (!confirmed) return;
    setDeletingVideoId(videoId);
    try {
      const result = await deleteVideo(videoId);
      await refreshRecent();
      clearVideo();
      setCurrentSourceBytes(null);
      const outputs = result.deleted_outputs ?? 0;
      const clipBytesFreed = result.deleted_bytes ?? 0;
      const outputBytesFreed = result.deleted_output_bytes ?? 0;
      const clipPart = clipBytesFreed > 0 ? ` Freed ${formatBytesVerbose(clipBytesFreed)} source media.` : "";
      const outputPart = outputs <= 0
        ? ""
        : outputs === 1
          ? ` Cleared 1 rendered output (${formatBytesVerbose(outputBytesFreed)}).`
          : ` Cleared ${outputs} rendered outputs (${formatBytesVerbose(outputBytesFreed)}).`;
      setProgress(0, `Removed ${label} from local library.${clipPart}${outputPart}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setProgress(0, `Delete failed: ${msg}`);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleLoadAdjacent = useCallback(async (direction: -1 | 1) => {
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered) return;
    let source = recentVideos;
    if (source.length <= 1) {
      try {
        const fresh = await listVideos();
        source = fresh;
        applyRecent(fresh);
      } catch {
        // best effort: continue with in-memory list when refresh fails
      }
    }
    if (source.length <= 1) {
      setProgress(0, source.length === 0 ? "No recent clips available." : "Only one clip available in Recent.");
      return;
    }
    let currentIndex = source.findIndex((item) => item.video_id === videoId);
    if (currentIndex < 0 && videoName) {
      currentIndex = source.findIndex((item) => item.filename === videoName);
    }
    const baseIndex = currentIndex >= 0
      ? currentIndex
      : direction > 0
        ? -1
        : 0;
    const nextIndex = ((baseIndex + direction) % source.length + source.length) % source.length;
    const next = source[nextIndex];
    await handleLoadExisting(next);
  }, [
    videoId,
    isAnalyzing,
    isRendering,
    deletingVideoId,
    renamingVideoId,
    refreshingRecent,
    clearingLibrary,
    clearingOutputs,
    pruningFiltered,
    recentVideos,
    videoName,
    applyRecent,
    setProgress,
    handleLoadExisting,
  ]);

  const handleRenameCurrent = async () => {
    if (!videoId || isAnalyzing || isRendering || deletingVideoId || renamingVideoId || clearingLibrary || clearingOutputs || pruningFiltered) return;
    await runRename(videoId, videoName || "clip.mp4");
  };

  useEffect(() => {
    const onAdjacentShortcut = (e: KeyboardEvent) => {
      if (!videoId || !e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || tag === "button" || target?.isContentEditable) return;
      if (e.code === "KeyP") {
        e.preventDefault();
        void handleLoadAdjacent(-1);
        return;
      }
      if (e.code === "KeyN") {
        e.preventDefault();
        void handleLoadAdjacent(1);
        return;
      }
      if (e.code === "KeyX") {
        e.preventDefault();
        handleClearVideo();
      }
    };
    window.addEventListener("keydown", onAdjacentShortcut, true);
    return () => window.removeEventListener("keydown", onAdjacentShortcut, true);
  }, [videoId, handleLoadAdjacent, handleClearVideo]);

  useEffect(() => {
    const onOutputShortcut = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "o") return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || tag === "button" || target?.isContentEditable) return;
      if (e.altKey && !e.shiftKey) {
        if (videoId || pruningFiltered || !hasActiveRecentSubset || !recentFetchDone || !filteredOutputCount || filteredOutputCount <= 0) return;
        e.preventDefault();
        void handleClearFilteredOutputs();
        return;
      }
      if (!e.shiftKey || e.altKey) return;
      if (videoId) {
        if (!clipOutputCount || clipOutputCount <= 0) return;
        e.preventDefault();
        void handleClearCurrentOutputs();
        return;
      }
      if (pruningFiltered || !recentFetchDone || !outputCount || outputCount <= 0) return;
      e.preventDefault();
      void handleClearAllOutputs();
    };
    window.addEventListener("keydown", onOutputShortcut, true);
    return () => window.removeEventListener("keydown", onOutputShortcut, true);
  }, [videoId, clipOutputCount, outputCount, recentFetchDone, pruningFiltered, hasActiveRecentSubset, filteredOutputCount, handleClearFilteredOutputs, handleClearCurrentOutputs, handleClearAllOutputs]);

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
        aria-keyshortcuts="Enter Space / Shift+/ O C S D R V Shift+V A 1 2 3 4 5 6 7 8 9 0 Control+Alt+O Meta+Alt+O"
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
                lib:{formatBytesShort(clipBytes)} · out:{outputCount ?? "?"} · mb:{formatBytesShort(outputBytes)}
              </span>
              {hasActiveRecentSubset && (
                <span className="text-[9px] font-pixel text-text-muted/70 text-center">
                  view:{formatBytesShort(filteredSourceBytes)} · out:{filteredOutputCount} · mb:{formatBytesShort(filteredOutputBytes)}
                </span>
              )}
              <button
                onClick={() => void refreshRecent()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label="Refresh local clip library"
                aria-keyshortcuts="R"
              >
                {refreshingRecent ? "[refreshing...]" : "[refresh]"}
              </button>
              <button
                onClick={() => void handleClearLibrary()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered || recentVideos.length === 0}
                className="text-[9px] font-pixel text-magenta-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label="Clear all local clips"
              >
                {clearingLibrary ? "[clearing...]" : "[clear all]"}
              </button>
              {hasActiveRecentSubset && (
                <button
                  onClick={() => void handleClearFiltered()}
                  disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered || filteredRecent.length === 0}
                  className="text-[9px] font-pixel text-magenta-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                  aria-label={`Clear ${filteredRecent.length} filtered clip${filteredRecent.length === 1 ? "" : "s"}`}
                >
                  {pruningFiltered ? "[clearing filt...]" : "[clear filtered]"}
                </button>
              )}
              {hasActiveRecentSubset && (
                <button
                  onClick={() => void handleClearFilteredOutputs()}
                  disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered || filteredOutputCount <= 0}
                  className="text-[9px] font-pixel text-amber-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                  aria-label={`Clear rendered outputs for filtered clips (${filteredOutputCount} outputs across ${filteredClipsWithOutputs} clips)`}
                  aria-keyshortcuts="Control+Alt+O Meta+Alt+O"
                >
                  {clearingFilteredOutputs ? "[clearing filt out...]" : "[clear filt out]"}
                </button>
              )}
              <button
                onClick={() => void handleClearAllOutputs()}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered || outputCount === 0}
                className="text-[9px] font-pixel text-magenta-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label="Clear all rendered outputs"
                aria-keyshortcuts="Control+Shift+O Meta+Shift+O"
              >
                {clearingOutputs && !clearingFilteredOutputs ? "[clearing out...]" : "[clear outputs]"}
              </button>
              {filteredRecent.length > RECENT_PREVIEW_LIMIT && (
                <button
                  onClick={() => setShowAllRecent((prev) => !prev)}
                  disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                  className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                  aria-label={showAllRecent ? "Show fewer recent clips" : "Show all recent clips"}
                  aria-keyshortcuts="A"
                >
                  {showAllRecent ? "[show less]" : "[show all]"}
                </button>
              )}
              <button
                onClick={cycleRecentSort}
                disabled={recentVideos.length <= 1 || isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label={`Sort recent clips (currently ${recentSort})`}
                aria-keyshortcuts="S"
              >
                [sort:{recentSort}]
              </button>
              <button
                onClick={() => setRecentSortReversed((prev) => !prev)}
                disabled={recentVideos.length <= 1 || isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label={`Toggle reverse order for recent clips (currently ${recentSortReversed ? "on" : "off"})`}
                aria-keyshortcuts="D"
              >
                [rev:{recentSortReversed ? "on" : "off"}]
              </button>
              <button
                onClick={() => {
                  setRecentOutputScope((prev) => {
                    if (prev === "all") return "with";
                    if (prev === "with") return "none";
                    return "all";
                  });
                }}
                disabled={recentVideos.length === 0 || isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label={`Filter recent clips by output count (currently ${recentOutputScope}, ${outputScopeCount} clips)`}
                aria-keyshortcuts="O"
              >
                [out:{recentOutputScope}:{outputScopeCount}]
              </button>
              <button
                onClick={() => {
                  setRecentCacheScope((prev) => {
                    if (prev === "all") return "cached";
                    if (prev === "cached") return "uncached";
                    return "all";
                  });
                }}
                disabled={recentVideos.length === 0 || isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label={`Filter recent clips by analysis cache state (currently ${recentCacheScope}, ${cacheScopeCount} clips)`}
                aria-keyshortcuts="C"
              >
                [cache:{recentCacheScope}:{cacheScopeCount}]
              </button>
              <button
                onClick={() => setShowShortcutHelp((prev) => !prev)}
                disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                aria-label={`${showShortcutHelp ? "Hide" : "Show"} dropzone keyboard shortcuts help`}
                aria-keyshortcuts="Shift+/"
              >
                [keys:{showShortcutHelp ? "on" : "off"}]
              </button>
              {hasActiveRecentSubset && (
                <button
                  onClick={resetRecentView}
                  disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                  className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                  aria-label="Reset recent view filters to all"
                  aria-keyshortcuts="V"
                >
                  [reset view]
                </button>
              )}
              {hasAnyRecentCustomization && (
                <button
                  onClick={resetRecentViewAll}
                  disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
                  className="text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed disabled:hover:text-text-muted"
                  aria-label="Reset recent view, sort, and expansion preferences to defaults"
                  aria-keyshortcuts="Shift+V"
                >
                  [reset all]
                </button>
              )}
            </div>
            {recentVideos.length > 0 && (
              <div className="flex items-center justify-center gap-1">
                <input
                  ref={recentFilterInputRef}
                  value={recentFilter}
                  onChange={(e) => setRecentFilter(e.target.value)}
                  onFocus={() => setRecentFilterFocused(true)}
                  onBlur={() => setRecentFilterFocused(false)}
                  onKeyDown={(e) => {
                    if (e.key === "Tab" && !e.shiftKey && recentTagSuggestions.length > 0) {
                      e.preventDefault();
                      applyRecentTagSuggestion(recentTagSuggestions[0]);
                      return;
                    }
                    if (e.key === "Backspace" && e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
                      e.preventDefault();
                      popRecentFilterTerm();
                      return;
                    }
                    if (e.key === "ArrowDown") {
                      if (visibleRecent.length <= 0) return;
                      e.preventDefault();
                      setRecentCursorIdx((prev) => {
                        if (prev < 0) return 0;
                        if (prev >= visibleRecent.length - 1) return 0;
                        return prev + 1;
                      });
                      return;
                    }
                    if (e.key === "ArrowUp") {
                      if (visibleRecent.length <= 0) return;
                      e.preventDefault();
                      setRecentCursorIdx((prev) => {
                        if (prev < 0) return visibleRecent.length - 1;
                        if (prev <= 0) return visibleRecent.length - 1;
                        return prev - 1;
                      });
                      return;
                    }
                    if (e.key === "Enter") {
                      e.preventDefault();
                      if (recentTagSuggestions.length > 0 && !recentFilter.endsWith(" ")) {
                        applyRecentTagSuggestion(recentTagSuggestions[0]);
                        return;
                      }
                      if (visibleRecent.length <= 0) {
                        setProgress(0, "No matching clips to load.");
                        return;
                      }
                      const targetIndex = recentCursorIdx >= 0
                        ? Math.min(recentCursorIdx, visibleRecent.length - 1)
                        : 0;
                      void handleLoadExisting(visibleRecent[targetIndex]);
                      return;
                    }
                    if (e.key === "Escape") {
                      e.preventDefault();
                      setRecentFilter("");
                      setRecentCursorIdx(-1);
                      e.currentTarget.blur();
                    }
                  }}
                  placeholder="filter clips (+term -term #tag)"
                  aria-label="Filter recent clips by terms (space-separated include/exclude and optional tags like #cached or #out)"
                  aria-keyshortcuts="Alt+Backspace Tab"
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
            {recentTagSuggestions.length > 0 && (
              <div className="flex flex-wrap justify-center items-center gap-1 text-[9px] font-pixel">
                {recentTagSuggestions.map((suggestion) => (
                  <button
                    key={`sugg-${suggestion}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => applyRecentTagSuggestion(suggestion)}
                    className="px-1.5 py-0.5 rounded border border-cyan-500/30 text-cyan-200/90 hover:text-white hover:border-cyan-400/80"
                    aria-label={`Apply tag suggestion ${suggestion}`}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            {recentFilterFocused && recentFilter.trim().length === 0 && recentTagSuggestions.length === 0 && (
              <div className="flex flex-wrap justify-center items-center gap-1 text-[9px] font-pixel">
                {RECENT_FILTER_TAGS.map((tag) => (
                  <button
                    key={`quick-${tag}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => applyRecentTagSuggestion(tag)}
                    className="px-1.5 py-0.5 rounded border border-cyan-500/25 text-cyan-200/80 hover:text-white hover:border-cyan-400/80"
                    aria-label={`Insert filter tag ${tag}`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}
            {parsedRecentFilterTerms.length > 0 && (
              <div className="flex flex-wrap justify-center items-center gap-1 text-[8px] font-pixel">
                {parsedRecentFilterTerms.map((item) => (
                  <button
                    key={`term-${item.idx}-${item.raw}`}
                    onClick={() => removeRecentFilterTerm(item.idx)}
                    className={`px-1 py-0.5 rounded border hover:text-white ${
                      item.isExclude
                        ? "border-amber-500/30 text-amber-200/90 hover:border-amber-400/70"
                        : "border-cyan-500/30 text-cyan-200/90 hover:border-cyan-400/70"
                    }`}
                    aria-label={`Remove ${item.isExclude ? "exclude" : "include"} term ${item.term} from filter`}
                    title={`Remove ${item.isExclude ? "-" : "+"}${item.term} from filter`}
                  >
                    {item.isExclude ? "-" : "+"}
                    {item.term}
                  </button>
                ))}
              </div>
            )}
            {showShortcutHelp && (
              <div className="text-[8px] font-pixel text-cyan-300/80 text-center px-2 leading-tight">
                keys: ? toggle · / focus filter · Enter load · ↑↓ select · #tag + Tab complete · Alt+Backspace pop filter term · 1-0 quick load (0=10th) · O out · C cache · S sort · D reverse · R refresh · A expand · V reset subset · Shift+V reset all · loaded: Alt+P/N cycle, Alt+X eject
              </div>
            )}
            {visibleRecent.length > 0 ? (
              <div className="flex flex-wrap justify-center gap-1">
                {visibleRecent.map((item, idx) => (
                  <div key={item.video_id} className="flex items-center gap-0.5">
                    {idx < 10 && (
                      <span className="text-[8px] font-pixel text-cyan-300/80 px-0.5" aria-hidden>
                        {idx === 9 ? "0" : idx + 1}
                      </span>
                    )}
                    <button
                      onClick={() => void handleLoadExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
                      className={`retro-btn px-2 py-0.5 text-[10px] font-pixel tracking-wide max-w-[180px] truncate disabled:opacity-50 disabled:cursor-not-allowed ${idx === recentCursorIdx ? "border-cyan-200 text-cyan-100 shadow-[0_0_0_1px_rgba(0,229,255,0.75),0_0_10px_rgba(0,229,255,0.45)]" : ""}`}
                      title={`${item.filename} · ${item.info.duration.toFixed(1)}s · src ${formatBytesVerbose(item.source_bytes)}${item.cached ? " · cached analysis" : ""} · ${item.output_count} output${item.output_count === 1 ? "" : "s"} (${formatBytesVerbose(item.output_bytes)})`}
                      aria-label={`${idx === recentCursorIdx ? "Selected: " : ""}Load ${item.filename}`}
                      aria-keyshortcuts={idx < 10 ? (idx === 9 ? "0" : String(idx + 1)) : undefined}
                      aria-current={idx === recentCursorIdx ? "true" : undefined}
                    >
                      {idx === recentCursorIdx ? "▶ " : ""}
                      {item.cached ? "⚡ " : ""}
                      {shortName(item.filename)}
                    </button>
                    <button
                      onClick={() => void handleRenameExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
                      className="text-[10px] font-pixel px-1 py-0.5 border rounded border-cyan-400/40 text-cyan-200 hover:text-white hover:border-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      title={`Rename ${item.filename}`}
                      aria-label={`Rename ${item.filename}`}
                    >
                      ✎
                    </button>
                    <button
                      onClick={() => void handleClearOutputsForExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered || item.output_count <= 0}
                      className="text-[10px] font-pixel px-1 py-0.5 border rounded border-amber-400/40 text-amber-200 hover:text-white hover:border-amber-300 disabled:opacity-50 disabled:cursor-not-allowed"
                      title={item.output_count > 0
                        ? `Clear ${item.output_count} rendered output${item.output_count === 1 ? "" : "s"} for ${item.filename}`
                        : `No rendered outputs for ${item.filename}`}
                      aria-label={item.output_count > 0
                        ? `Clear rendered outputs for ${item.filename}`
                        : `No rendered outputs for ${item.filename}`}
                    >
                      {`◍${item.output_count > 0 ? item.output_count : ""}`}
                    </button>
                    <button
                      onClick={() => void handleDeleteExisting(item)}
                      disabled={deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
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
        src:{formatBytesShort(currentSourceBytes)}/{formatBytesShort(clipBytes)}
      </span>
      <span className="text-[10px] font-pixel text-text-muted/70 whitespace-nowrap">
        out:{clipOutputCount ?? "?"}/{outputCount ?? "?"} · mb:{formatBytesShort(clipOutputBytes)}/{formatBytesShort(outputBytes)}
      </span>
      <Tooltip text="Clear current clip and return to upload/recent selector">
        <button
          onClick={handleClearVideo}
          disabled={isAnalyzing || isRendering || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-text-muted hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
          aria-keyshortcuts="Alt+X"
        >
          [EJECT]
        </button>
      </Tooltip>
      <Tooltip text="Load previous recent clip">
        <button
          onClick={() => void handleLoadAdjacent(-1)}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-cyan-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase px-1 py-0.5 border border-cyan-400/35 rounded"
          aria-keyshortcuts="Alt+P"
        >
          [PREV]
        </button>
      </Tooltip>
      <Tooltip text="Load next recent clip">
        <button
          onClick={() => void handleLoadAdjacent(1)}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || refreshingRecent || clearingLibrary || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-cyan-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase px-1 py-0.5 border border-cyan-400/35 rounded"
          aria-keyshortcuts="Alt+N"
        >
          [NEXT]
        </button>
      </Tooltip>
      <Tooltip text="Replace the current video with a new one">
        <button
          onClick={openPicker}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-neon-magenta hover:text-white retro-glow-magenta shrink-0 uppercase disabled:opacity-40 disabled:cursor-not-allowed"
        >
          [SWAP]
        </button>
      </Tooltip>
      <Tooltip text="Delete this clip from local library and clear the current session">
        <button
          onClick={() => void handleDeleteCurrent()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [DELETE]
        </button>
      </Tooltip>
      <Tooltip text="Rename current clip label in local library">
        <button
          onClick={() => void handleRenameCurrent()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-cyan-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [RENAME]
        </button>
      </Tooltip>
      <Tooltip text="Remove every clip from local library and reset to upload screen">
        <button
          onClick={() => void handleClearLibrary()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
        >
          [CLEAR LIB]
        </button>
      </Tooltip>
      <Tooltip text="Delete rendered outputs for current clip only">
        <button
          onClick={() => void handleClearCurrentOutputs()}
          disabled={isAnalyzing || isRendering || deletingVideoId !== null || renamingVideoId !== null || clearingLibrary || clearingOutputs || pruningFiltered || !clipOutputCount || clipOutputCount <= 0}
          className="text-[11px] font-pixel text-magenta-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed shrink-0 uppercase"
          aria-keyshortcuts="Control+Shift+O Meta+Shift+O"
        >
          {clearingOutputs ? "[CLEARING OUT]" : "[CLEAR OUT]"}
        </button>
      </Tooltip>
    </div>
  );
}
