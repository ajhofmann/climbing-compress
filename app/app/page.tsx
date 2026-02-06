"use client";

import { useCallback, useEffect, useRef } from "react";
import { useStore, AnalysisParams } from "@/lib/store";
import { analyzeVideo, solveCurve, renderVideo, previewVideo } from "@/lib/api";
import { VideoUpload } from "@/components/video-upload";
import { VideoPlayer } from "@/components/video-player";
import { TimelineEditor } from "@/components/timeline-editor";
import { DebugCharts } from "@/components/debug-charts";
import { SettingsPanel } from "@/components/settings";
import { ProgressBar } from "@/components/progress-bar";
import { Tooltip } from "@/components/tooltip";
import { HeaderArt } from "@/components/header-art";
import { ProjectManager } from "@/components/project-manager";
import { SystemMetrics } from "@/components/system-metrics";
import { JobMonitor } from "@/components/job-monitor";
import { VideoLibrary } from "@/components/video-library";
import { OutputHistory } from "@/components/output-history";

export default function Home() {
  const store = useStore();
  const solveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { videoId, analysis, settings, pins, playbackTime } = store;

  useEffect(() => {
    if (!videoId || !analysis) return;
    if (solveTimeout.current) clearTimeout(solveTimeout.current);
    solveTimeout.current = setTimeout(async () => {
      try {
        const result = await solveCurve(videoId, settings, pins);
        store.setCurve(result.curve, result.times, result.stats, result.scores, result.rest_regions);
      } catch (e) {
        console.error("solve:", e);
      }
    }, 80);
    return () => { if (solveTimeout.current) clearTimeout(solveTimeout.current); };
  }, [videoId, analysis, settings, pins]);

  const handleAnalyze = useCallback(async () => {
    if (!videoId) return;
    const currentParams: AnalysisParams = {
      stride: settings.analyzeStride,
      useTracker: settings.useTracker,
      useFlow: settings.useFlow,
    };
    const cached = store.analysisParams;
    const paramsMatch = cached && cached.stride === currentParams.stride && cached.useTracker === currentParams.useTracker && cached.useFlow === currentParams.useFlow;
    const force = !!(analysis && paramsMatch);
    store.setAnalyzing(true);
    store.setProgress(0, force ? "Re-analyzing (fresh)..." : "Starting analysis...");
    try {
      const result = await analyzeVideo(videoId, settings.analyzeStride, force, (p, msg) => { store.setProgress(p, msg); }, settings.useTracker, settings.useFlow, settings.trackerModel);
      if (result) {
        store.setAnalysis(result, currentParams);
        if (settings.trimEnd === 0) store.updateSettings({ trimEnd: result.duration });
        store.setProgress(0.95, "Computing speed curve...");
        const updatedSettings = { ...settings, trimEnd: settings.trimEnd === 0 ? result.duration : settings.trimEnd };
        const solveResult = await solveCurve(videoId, updatedSettings, pins);
        store.setCurve(solveResult.curve, solveResult.times, solveResult.stats, solveResult.scores, solveResult.rest_regions);
        store.setProgress(0, "Analysis complete!");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      store.setProgress(0, `Error: ${msg}`);
    } finally {
      store.setAnalyzing(false);
    }
  }, [videoId, analysis, settings, pins]);

  const handleRender = useCallback(async () => {
    if (!videoId) return;
    store.setRendering(true);
    store.setProgress(0, "Starting render...");
    try {
      const result = await renderVideo(videoId, settings, pins, (p, msg) => { store.setProgress(p, msg); });
      if (result?.output_id) {
        store.setOutputId(result.output_id);
        store.setComparisonId(result.comparison_id ?? null);
        store.setProgress(0, `Done! ${result.stats?.output_duration}s video ready`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      store.setProgress(0, `Error: ${msg}`);
    } finally {
      store.setRendering(false);
    }
  }, [videoId, settings, pins]);

  const handlePreview = useCallback(async () => {
    if (!videoId || !analysis) return;
    const previewDuration = 4;
    const end = settings.trimEnd > 0 ? settings.trimEnd : analysis.duration;
    const baseStart = playbackTime > 0 ? playbackTime : settings.trimStart;
    const start = Math.max(settings.trimStart, Math.min(baseStart, Math.max(end - previewDuration, 0)));
    store.setPreviewing(true);
    store.setProgress(0, "Starting preview...");
    try {
      const result = await previewVideo(
        videoId,
        settings,
        pins,
        start,
        previewDuration,
        (p, msg) => { store.setProgress(p, msg); },
      );
      if (result?.output_id) {
        store.setPreviewId(result.output_id);
        store.setProgress(0, "Preview ready");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      store.setProgress(0, `Error: ${msg}`);
    } finally {
      store.setPreviewing(false);
    }
  }, [videoId, analysis, settings, pins, playbackTime]);

  const hasAnalysis = !!analysis;

  return (
    <main className="max-w-[1400px] mx-auto px-8 py-6 flex flex-col gap-4">
      {/* Header */}
      <HeaderArt />

      <ProjectManager />
      <SystemMetrics />
      <JobMonitor />
      <VideoLibrary />
      <OutputHistory />

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
                  disabled={!videoId || store.isAnalyzing}
                  className={`px-5 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    store.isAnalyzing ? "retro-btn-primary opacity-70"
                      : videoId && !hasAnalysis ? "retro-btn-primary pulse-border"
                      : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                >
                  {store.isAnalyzing ? "ANALYZING..." : hasAnalysis ? "RE-ANALYZE" : "ANALYZE"}
                </button>
              </Tooltip>
              <div className="flex-1 min-w-0">
                <ProgressBar />
              </div>
              {/* Video info inline */}
              <VideoUpload />
              <Tooltip text={"Quick low-res preview around\nthe current playhead.\nGreat for checking timing."}>
                <button
                  onClick={handlePreview}
                  disabled={!videoId || !hasAnalysis || store.isPreviewing}
                  className={`px-4 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    store.isPreviewing ? "retro-btn opacity-70" : hasAnalysis ? "retro-btn" : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                >
                  {store.isPreviewing ? "PREVIEWING..." : "PREVIEW"}
                </button>
              </Tooltip>
              <Tooltip text={"Export the speed-ramped video using\nyour current curve and settings.\nIncludes stabilization, audio, and overlays\nif enabled in the Output panel."}>
                <button
                  onClick={handleRender}
                  disabled={!videoId || !hasAnalysis || store.isRendering}
                  className={`px-5 py-1.5 rounded text-xs font-pixel uppercase tracking-widest transition-all whitespace-nowrap ${
                    store.isRendering ? "retro-btn opacity-70" : hasAnalysis ? "retro-btn-primary" : "retro-btn"
                  } disabled:opacity-30 disabled:cursor-not-allowed`}
                  style={store.isRendering ? { borderColor: "var(--neon-orange)", color: "var(--neon-orange)", textShadow: "0 0 8px rgba(255,110,64,0.5)" } : {}}
                >
                  {store.isRendering ? "RENDERING..." : "RENDER"}
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
