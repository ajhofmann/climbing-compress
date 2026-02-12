"use client";

import { useCallback, useEffect, useRef } from "react";
import { useStore, AnalysisParams } from "@/lib/store";
import { analyzeVideo, solveCurve, renderVideo } from "@/lib/api";
import { VideoUpload } from "@/components/video-upload";
import { VideoPlayer } from "@/components/video-player";
import { TimelineEditor } from "@/components/timeline-editor";
import { RenderHistoryTimeline } from "@/components/render-history";
import { SettingsPanel } from "@/components/settings";
import { ProgressBar } from "@/components/progress-bar";
import { Tooltip } from "@/components/tooltip";
import { HeaderArt } from "@/components/header-art";

export default function Home() {
  const videoId = useStore((s) => s.videoId);
  const analysis = useStore((s) => s.analysis);
  const analysisParams = useStore((s) => s.analysisParams);
  const settings = useStore((s) => s.settings);
  const pins = useStore((s) => s.pins);
  const keyframes = useStore((s) => s.keyframes);
  const isAnalyzing = useStore((s) => s.isAnalyzing);
  const isRendering = useStore((s) => s.isRendering);

  const setCurve = useStore((s) => s.setCurve);
  const setAnalysis = useStore((s) => s.setAnalysis);
  const setAnalyzing = useStore((s) => s.setAnalyzing);
  const setRendering = useStore((s) => s.setRendering);
  const setProgress = useStore((s) => s.setProgress);
  const updateSettings = useStore((s) => s.updateSettings);
  const setOutputId = useStore((s) => s.setOutputId);
  const setComparisonId = useStore((s) => s.setComparisonId);

  const solveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoSolveAbortRef = useRef<AbortController | null>(null);
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const analyzeSolveAbortRef = useRef<AbortController | null>(null);
  const analyzeRunRef = useRef(0);
  const renderAbortRef = useRef<AbortController | null>(null);
  const renderRunRef = useRef(0);
  const suspendAutoSolveRef = useRef(false);

  const isAbortError = (e: unknown) => e instanceof Error && e.name === "AbortError";

  useEffect(() => {
    return () => {
      analyzeAbortRef.current?.abort();
      analyzeSolveAbortRef.current?.abort();
      autoSolveAbortRef.current?.abort();
      renderAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!videoId || !analysis || suspendAutoSolveRef.current) return;
    if (solveTimeout.current) clearTimeout(solveTimeout.current);
    autoSolveAbortRef.current?.abort();
    solveTimeout.current = setTimeout(async () => {
      const controller = new AbortController();
      autoSolveAbortRef.current = controller;
      try {
        const result = await solveCurve(videoId, settings, pins, keyframes, controller.signal);
        if (controller.signal.aborted) return;
        setCurve(result.curve, result.times, result.stats, result.scores, result.rest_regions, result.crux_points);
      } catch (e) {
        if (isAbortError(e)) return;
        console.error("solve:", e);
      } finally {
        if (autoSolveAbortRef.current === controller) {
          autoSolveAbortRef.current = null;
        }
      }
    }, 80);
    return () => {
      if (solveTimeout.current) clearTimeout(solveTimeout.current);
      autoSolveAbortRef.current?.abort();
    };
  }, [videoId, analysis, settings, pins, keyframes, setCurve]);

  const handleAnalyze = useCallback(async () => {
    if (!videoId) return;
    const runId = analyzeRunRef.current + 1;
    analyzeRunRef.current = runId;
    suspendAutoSolveRef.current = true;
    analyzeAbortRef.current?.abort();
    analyzeSolveAbortRef.current?.abort();
    autoSolveAbortRef.current?.abort();
    const analyzeController = new AbortController();
    analyzeAbortRef.current = analyzeController;
    let solveController: AbortController | null = null;

    const currentParams: AnalysisParams = {
      stride: settings.analyzeStride,
      useTracker: settings.useTracker,
      useFlow: settings.useFlow,
    };
    const cached = analysisParams;
    const paramsMatch = cached && cached.stride === currentParams.stride && cached.useTracker === currentParams.useTracker && cached.useFlow === currentParams.useFlow;
    const force = !!(analysis && paramsMatch);
    setAnalyzing(true);
    setProgress(0, force ? "Re-analyzing (fresh)..." : "Starting analysis...");
    try {
      const result = await analyzeVideo(
        videoId,
        settings.analyzeStride,
        force,
        (p, msg) => {
          if (analyzeRunRef.current !== runId) return;
          setProgress(p, msg);
        },
        settings.useTracker,
        settings.useFlow,
        settings.trackerModel,
        analyzeController.signal,
      );
      if (analyzeController.signal.aborted || analyzeRunRef.current !== runId) return;
      if (result) {
        setAnalysis(result, currentParams);
        if (settings.trimEnd === 0) updateSettings({ trimEnd: result.duration });
        if (analyzeRunRef.current !== runId) return;
        setProgress(0.95, "Computing speed curve...");
        const updatedSettings = { ...settings, trimEnd: settings.trimEnd === 0 ? result.duration : settings.trimEnd };
        solveController = new AbortController();
        analyzeSolveAbortRef.current = solveController;
        const solveResult = await solveCurve(videoId, updatedSettings, pins, keyframes, solveController.signal);
        if (solveController.signal.aborted || analyzeRunRef.current !== runId) return;
        setCurve(solveResult.curve, solveResult.times, solveResult.stats, solveResult.scores, solveResult.rest_regions, solveResult.crux_points);
        setProgress(0, "Analysis complete!");
      }
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      if (analyzeRunRef.current !== runId) return;
      const msg = e instanceof Error ? e.message : "Unknown error";
      setProgress(0, `Error: ${msg}`);
    } finally {
      if (analyzeSolveAbortRef.current === solveController) {
        analyzeSolveAbortRef.current = null;
      }
      if (analyzeRunRef.current === runId && analyzeAbortRef.current === analyzeController) {
        analyzeAbortRef.current = null;
        suspendAutoSolveRef.current = false;
        setAnalyzing(false);
      }
    }
  }, [videoId, analysis, analysisParams, settings, pins, keyframes, setAnalyzing, setProgress, setAnalysis, updateSettings, setCurve]);

  const handleCancelAnalyze = useCallback(() => {
    analyzeRunRef.current += 1;
    if (solveTimeout.current) {
      clearTimeout(solveTimeout.current);
      solveTimeout.current = null;
    }
    autoSolveAbortRef.current?.abort();
    autoSolveAbortRef.current = null;
    analyzeSolveAbortRef.current?.abort();
    analyzeSolveAbortRef.current = null;
    analyzeAbortRef.current?.abort();
    analyzeAbortRef.current = null;
    suspendAutoSolveRef.current = false;
    setAnalyzing(false);
    setProgress(0, "Analysis cancelled");
  }, [setAnalyzing, setProgress]);

  const handleRender = useCallback(async () => {
    if (!videoId) return;
    renderAbortRef.current?.abort();
    const renderController = new AbortController();
    renderAbortRef.current = renderController;
    const runId = renderRunRef.current + 1;
    renderRunRef.current = runId;
    setRendering(true);
    setProgress(0, "Starting render...");
    try {
      const result = await renderVideo(
        videoId,
        settings,
        pins,
        keyframes,
        (p, msg) => {
          if (renderRunRef.current !== runId) return;
          setProgress(p, msg);
        },
        renderController.signal,
      );
      if (renderController.signal.aborted || renderRunRef.current !== runId) return;
      if (result?.output_id) {
        setOutputId(result.output_id);
        setComparisonId(result.comparison_id ?? null);
        setProgress(0, `Done! ${result.stats?.output_duration}s video ready`);
      }
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const msg = e instanceof Error ? e.message : "Unknown error";
      setProgress(0, `Error: ${msg}`);
    } finally {
      if (renderRunRef.current === runId && renderAbortRef.current === renderController) {
        renderAbortRef.current = null;
        setRendering(false);
      }
    }
  }, [videoId, settings, pins, keyframes, setRendering, setProgress, setOutputId, setComparisonId]);

  const handleQuickRender = useCallback(async () => {
    if (!videoId) return;
    renderAbortRef.current?.abort();
    const renderController = new AbortController();
    renderAbortRef.current = renderController;
    const runId = renderRunRef.current + 1;
    renderRunRef.current = runId;
    setRendering(true);
    setProgress(0, "Starting quick preview render...");
    try {
      const draftSettings = {
        ...settings,
        scale: Math.min(settings.scale, 0.35),
        outputFps: Math.min(settings.outputFps, 24),
        crf: Math.max(settings.crf, 30),
        includeAudio: false,
        debugOverlay: false,
        renderComparison: false,
      };
      const result = await renderVideo(
        videoId,
        draftSettings,
        pins,
        keyframes,
        (p, msg) => {
          if (renderRunRef.current !== runId) return;
          setProgress(p, `[preview] ${msg}`);
        },
        renderController.signal,
      );
      if (renderController.signal.aborted || renderRunRef.current !== runId) return;
      if (result?.output_id) {
        setOutputId(result.output_id);
        setComparisonId(null);
        setProgress(0, "Quick preview ready");
      }
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const msg = e instanceof Error ? e.message : "Unknown error";
      setProgress(0, `Error: ${msg}`);
    } finally {
      if (renderRunRef.current === runId && renderAbortRef.current === renderController) {
        renderAbortRef.current = null;
        setRendering(false);
      }
    }
  }, [videoId, settings, pins, keyframes, setRendering, setProgress, setOutputId, setComparisonId]);

  const handleCancelRender = useCallback(() => {
    renderRunRef.current += 1;
    renderAbortRef.current?.abort();
    renderAbortRef.current = null;
    setRendering(false);
    setProgress(0, "Render cancelled");
  }, [setRendering, setProgress]);

  useEffect(() => {
    if (!isRendering) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleCancelRender();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isRendering, handleCancelRender]);

  const hasAnalysis = !!analysis;

  const handleTransportShortcuts = useCallback((e: KeyboardEvent) => {
    const target = e.target as HTMLElement | null;
    const tag = target?.tagName;
    if (target?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON") return;

    if (!(e.ctrlKey || e.metaKey)) return;

    const key = e.key.toLowerCase();

    if (key === "a" && e.shiftKey) {
      if (!videoId || isRendering) return;
      e.preventDefault();
      if (isAnalyzing) {
        handleCancelAnalyze();
      } else {
        handleAnalyze();
      }
      return;
    }

    if (e.key === "Enter") {
      if (!videoId || !hasAnalysis || isAnalyzing || isRendering) return;
      e.preventDefault();
      if (e.shiftKey) {
        handleRender();
      } else {
        handleQuickRender();
      }
    }
  }, [
    videoId,
    hasAnalysis,
    isAnalyzing,
    isRendering,
    handleAnalyze,
    handleCancelAnalyze,
    handleRender,
    handleQuickRender,
  ]);

  useEffect(() => {
    window.addEventListener("keydown", handleTransportShortcuts);
    return () => window.removeEventListener("keydown", handleTransportShortcuts);
  }, [handleTransportShortcuts]);

  return (
    <main className="max-w-[1400px] mx-auto px-8 py-6 flex flex-col gap-4">
      {/* Header */}
      <HeaderArt />

      {/* Video output -- appears at top once rendered */}
      <VideoPlayer />
      <div className="neon-divider w-full" />

      {/* Transport + Timeline (doubles as upload zone when no video) */}
      <div className="px-3 py-2 retro-panel rounded">
        {!videoId ? (
          <VideoUpload />
        ) : (
          <>
            {/* Clip info bar */}
            <VideoUpload />

            {/* Transport bar */}
            <div className="flex items-center gap-3 mt-2 mb-2">
              <Tooltip text={"Detect the climber's pose in every frame.\nComputes movement scores and identifies\nrest vs action sections of the climb.\nShortcut: Ctrl/Cmd + Shift + A"}>
                <button
                  onClick={isAnalyzing ? handleCancelAnalyze : handleAnalyze}
                  disabled={!videoId}
                  aria-keyshortcuts="Control+Shift+A Meta+Shift+A"
                  className={`px-5 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    isAnalyzing ? "retro-btn"
                      : videoId && !hasAnalysis ? "retro-btn-primary pulse-border"
                      : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                  style={isAnalyzing ? {
                    borderColor: "var(--danger)",
                    color: "var(--danger)",
                    textShadow: "0 0 8px rgba(255,23,68,0.35)",
                  } : {}}
                >
                  {isAnalyzing ? "CANCEL" : hasAnalysis ? "RE-ANALYZE" : "ANALYZE"}
                </button>
              </Tooltip>
              <div className="flex-1 min-w-0">
                <ProgressBar />
              </div>
              <Tooltip text={"Fast local preview render.\nUses lower resolution + higher CRF + no audio\nfor rapid iteration while tuning curve edits.\nShortcut: Ctrl/Cmd + Enter"}>
                <button
                  onClick={handleQuickRender}
                  disabled={!videoId || !hasAnalysis || isRendering}
                  aria-keyshortcuts="Control+Enter Meta+Enter"
                  className={`px-4 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    hasAnalysis ? "retro-btn" : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                  style={hasAnalysis ? { borderColor: "var(--neon-magenta)", color: "var(--neon-magenta)", textShadow: "0 0 8px rgba(224,64,251,0.35)" } : {}}
                >
                  PREVIEW
                </button>
              </Tooltip>
              <Tooltip text={"Export the speed-ramped video using\nyour current curve and settings.\nIncludes stabilization, audio, and overlays\nif enabled in the Output panel.\nShortcut: Ctrl/Cmd + Shift + Enter"}>
                <button
                  onClick={handleRender}
                  disabled={!videoId || !hasAnalysis || isRendering}
                  aria-keyshortcuts="Control+Shift+Enter Meta+Shift+Enter"
                  className={`px-5 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    isRendering ? "retro-btn opacity-70" : hasAnalysis ? "retro-btn-primary" : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                  style={isRendering ? { borderColor: "var(--neon-orange)", color: "var(--neon-orange)", textShadow: "0 0 8px rgba(255,110,64,0.45)" } : {}}
                >
                  {isRendering ? "RENDERING..." : "RENDER"}
                </button>
              </Tooltip>
              {isRendering && (
                <button
                  onPointerDown={(e) => {
                    e.preventDefault();
                    handleCancelRender();
                  }}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleCancelRender();
                  }}
                  onClick={handleCancelRender}
                  aria-keyshortcuts="Escape"
                  className="px-3 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap retro-btn"
                  style={{ borderColor: "var(--danger)", color: "var(--danger)", textShadow: "0 0 8px rgba(255,23,68,0.45)" }}
                  title="Cancel the active render request (Esc also works)"
                >
                  CANCEL
                </button>
              )}
            </div>
            <TimelineEditor />
            <RenderHistoryTimeline videoId={videoId} />
          </>
        )}
      </div>

      <div className="neon-divider w-full" />
      {/* Settings Dashboard */}
      <SettingsPanel />

      {/* Footer */}
      <footer className="relative mt-4 pt-4 pb-3 flex flex-col items-center gap-3">
        <div className="neon-divider w-full" />

        {/* Mini synthwave grid decoration */}
        <svg className="opacity-15" width="240" height="28" viewBox="0 0 240 28">
          {Array.from({ length: 11 }).map((_, i) => (
            <line key={`v${i}`} x1={120 + (i - 5) * 4} y1={0} x2={120 + (i - 5) * 24} y2={28} stroke="#00e5ff" strokeWidth="0.5" opacity={0.5 - Math.abs(i - 5) * 0.07} />
          ))}
          {Array.from({ length: 4 }).map((_, i) => {
            const y = 4 + i * 8;
            const spread = 0.3 + (i / 3) * 0.7;
            return <line key={`h${i}`} x1={120 - 120 * spread} y1={y} x2={120 + 120 * spread} y2={y} stroke="#00e5ff" strokeWidth="0.4" opacity={0.25 + i * 0.05} />;
          })}
        </svg>

        <p
          className="text-xs font-pixel tracking-[0.2em] uppercase"
          style={{ color: "var(--neon-cyan)", opacity: 0.3, textShadow: "0 0 8px rgba(0,229,255,0.3)" }}
        >
          SENDIT v2.0 // SPEED RAMP SYSTEM
        </p>

        <div className="flex items-center gap-2 opacity-25">
          <span className="pilot-light pilot-light-cyan" style={{ width: 4, height: 4 }} />
          <span className="text-[8px] font-retro tracking-[0.2em]" style={{ color: "var(--chrome-dark)" }}>SYSTEM NOMINAL</span>
          <span className="pilot-light pilot-light-cyan" style={{ width: 4, height: 4 }} />
        </div>

        <div className="neon-divider-magenta w-48" />
      </footer>
    </main>
  );
}
