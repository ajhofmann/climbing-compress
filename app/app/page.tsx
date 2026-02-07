"use client";

import { useCallback, useEffect, useRef } from "react";
import { useStore, AnalysisParams } from "@/lib/store";
import { analyzeVideo, solveCurve, renderVideo } from "@/lib/api";
import { VideoUpload } from "@/components/video-upload";
import { VideoPlayer } from "@/components/video-player";
import { TimelineEditor } from "@/components/timeline-editor";
import { DebugCharts } from "@/components/debug-charts";
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

  useEffect(() => {
    if (!videoId || !analysis) return;
    if (solveTimeout.current) clearTimeout(solveTimeout.current);
    solveTimeout.current = setTimeout(async () => {
      try {
        const result = await solveCurve(videoId, settings, pins, keyframes);
        setCurve(result.curve, result.times, result.stats, result.scores, result.rest_regions, result.crux_points);
      } catch (e) {
        console.error("solve:", e);
      }
    }, 80);
    return () => { if (solveTimeout.current) clearTimeout(solveTimeout.current); };
  }, [videoId, analysis, settings, pins, keyframes, setCurve]);

  const handleAnalyze = useCallback(async () => {
    if (!videoId) return;
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
      const result = await analyzeVideo(videoId, settings.analyzeStride, force, (p, msg) => { setProgress(p, msg); }, settings.useTracker, settings.useFlow, settings.trackerModel);
      if (result) {
        setAnalysis(result, currentParams);
        if (settings.trimEnd === 0) updateSettings({ trimEnd: result.duration });
        setProgress(0.95, "Computing speed curve...");
        const updatedSettings = { ...settings, trimEnd: settings.trimEnd === 0 ? result.duration : settings.trimEnd };
        const solveResult = await solveCurve(videoId, updatedSettings, pins, keyframes);
        setCurve(solveResult.curve, solveResult.times, solveResult.stats, solveResult.scores, solveResult.rest_regions, solveResult.crux_points);
        setProgress(0, "Analysis complete!");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setProgress(0, `Error: ${msg}`);
    } finally {
      setAnalyzing(false);
    }
  }, [videoId, analysis, analysisParams, settings, pins, keyframes, setAnalyzing, setProgress, setAnalysis, updateSettings, setCurve]);

  const handleRender = useCallback(async () => {
    if (!videoId) return;
    setRendering(true);
    setProgress(0, "Starting render...");
    try {
      const result = await renderVideo(videoId, settings, pins, keyframes, (p, msg) => { setProgress(p, msg); });
      if (result?.output_id) {
        setOutputId(result.output_id);
        setComparisonId(result.comparison_id ?? null);
        setProgress(0, `Done! ${result.stats?.output_duration}s video ready`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setProgress(0, `Error: ${msg}`);
    } finally {
      setRendering(false);
    }
  }, [videoId, settings, pins, keyframes, setRendering, setProgress, setOutputId, setComparisonId]);

  const handleQuickRender = useCallback(async () => {
    if (!videoId) return;
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
      const result = await renderVideo(videoId, draftSettings, pins, keyframes, (p, msg) => { setProgress(p, `[preview] ${msg}`); });
      if (result?.output_id) {
        setOutputId(result.output_id);
        setComparisonId(null);
        setProgress(0, "Quick preview ready");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setProgress(0, `Error: ${msg}`);
    } finally {
      setRendering(false);
    }
  }, [videoId, settings, pins, keyframes, setRendering, setProgress, setOutputId, setComparisonId]);

  const hasAnalysis = !!analysis;

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
            {/* Transport bar */}
            <div className="flex items-center gap-3 mb-2">
              <Tooltip text={"Detect the climber's pose in every frame.\nComputes movement scores and identifies\nrest vs action sections of the climb."}>
                <button
                  onClick={handleAnalyze}
                  disabled={!videoId || isAnalyzing}
                  className={`px-5 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    isAnalyzing ? "retro-btn-primary opacity-70"
                      : videoId && !hasAnalysis ? "retro-btn-primary pulse-border"
                      : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                >
                  {isAnalyzing ? "ANALYZING..." : hasAnalysis ? "RE-ANALYZE" : "ANALYZE"}
                </button>
              </Tooltip>
              <div className="flex-1 min-w-0">
                <ProgressBar />
              </div>
              {/* Video info inline */}
              <VideoUpload />
              <Tooltip text={"Fast local preview render.\nUses lower resolution + higher CRF + no audio\nfor rapid iteration while tuning curve edits."}>
                <button
                  onClick={handleQuickRender}
                  disabled={!videoId || !hasAnalysis || isRendering}
                  className={`px-4 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    hasAnalysis ? "retro-btn" : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                  style={hasAnalysis ? { borderColor: "var(--neon-magenta)", color: "var(--neon-magenta)", textShadow: "0 0 8px rgba(224,64,251,0.35)" } : {}}
                >
                  QUICK PREVIEW
                </button>
              </Tooltip>
              <Tooltip text={"Export the speed-ramped video using\nyour current curve and settings.\nIncludes stabilization, audio, and overlays\nif enabled in the Output panel."}>
                <button
                  onClick={handleRender}
                  disabled={!videoId || !hasAnalysis || isRendering}
                  className={`px-5 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    isRendering ? "retro-btn opacity-70" : hasAnalysis ? "retro-btn-primary" : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                  style={isRendering ? { borderColor: "var(--neon-orange)", color: "var(--neon-orange)", textShadow: "0 0 8px rgba(255,110,64,0.5)" } : {}}
                >
                  {isRendering ? "RENDERING..." : "RENDER"}
                </button>
              </Tooltip>
            </div>
            <TimelineEditor />
          </>
        )}
      </div>

      <div className="neon-divider w-full" />
      {/* Settings Dashboard */}
      <SettingsPanel />

      {/* Debug Charts */}
      <DebugCharts />

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
