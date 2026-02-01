"use client";

import { useCallback, useEffect, useRef } from "react";
import { useStore, AnalysisParams } from "@/lib/store";
import { analyzeVideo, solveCurve, renderVideo } from "@/lib/api";
import { VideoUpload } from "@/components/video-upload";
import { VideoPlayer } from "@/components/video-player";
import { TimelineEditor } from "@/components/timeline-editor";
import { SettingsPanel } from "@/components/settings";
import { ProgressBar } from "@/components/progress-bar";

export default function Home() {
  const store = useStore();
  const solveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { videoId, analysis, settings, pins } = store;

  useEffect(() => {
    if (!videoId || !analysis) return;
    if (solveTimeout.current) clearTimeout(solveTimeout.current);
    solveTimeout.current = setTimeout(async () => {
      try {
        const result = await solveCurve(videoId, settings, pins);
        store.setCurve(result.curve, result.times, result.stats);
      } catch (e) {
        console.error("solve:", e);
      }
    }, 80);
    return () => { if (solveTimeout.current) clearTimeout(solveTimeout.current); };
  }, [videoId, analysis, settings, pins]);

  const handleAnalyze = useCallback(async () => {
    if (!videoId) return;

    // Check if analysis is already cached with the same params
    const currentParams: AnalysisParams = {
      stride: settings.analyzeStride,
      useTracker: settings.useTracker,
      useFlow: settings.useFlow,
    };
    const cached = store.analysisParams;
    if (
      analysis &&
      cached &&
      cached.stride === currentParams.stride &&
      cached.useTracker === currentParams.useTracker &&
      cached.useFlow === currentParams.useFlow
    ) {
      store.setProgress(0, "Analysis already up to date");
      return;
    }

    store.setAnalyzing(true);
    store.setProgress(0, "Starting analysis...");
    try {
      const result = await analyzeVideo(
        videoId, settings.analyzeStride, false,
        (p, msg) => { store.setProgress(p, msg); },
        settings.useTracker, settings.useFlow,
      );
      if (result) {
        store.setAnalysis(result, currentParams);
        if (settings.trimEnd === 0) {
          store.updateSettings({ trimEnd: result.duration });
        }
        store.setProgress(0.95, "Computing speed curve...");
        const updatedSettings = { ...settings, trimEnd: settings.trimEnd === 0 ? result.duration : settings.trimEnd };
        const solveResult = await solveCurve(videoId, updatedSettings, pins);
        store.setCurve(solveResult.curve, solveResult.times, solveResult.stats);
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
      const result = await renderVideo(videoId, settings, pins, (p, msg) => {
        store.setProgress(p, msg);
      });
      if (result?.output_id) {
        store.setOutputId(result.output_id);
        store.setProgress(0, `Done! ${result.stats?.output_duration}s video ready`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      store.setProgress(0, `Error: ${msg}`);
    } finally {
      store.setRendering(false);
    }
  }, [videoId, settings, pins]);

  const hasAnalysis = !!analysis;

  return (
    <main className="max-w-4xl mx-auto px-6 py-12 flex flex-col gap-8">
      {/* Header */}
      <header>
        <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--accent)" }}>
          climb-ramp
        </h1>
        <p className="text-sm text-text-muted mt-0.5">
          speed-ramp your sends
        </p>
      </header>

      {/* Video I/O */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <VideoUpload />
        <VideoPlayer />
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3">
        <div className="flex gap-3">
          <button
            onClick={handleAnalyze}
            disabled={!videoId || store.isAnalyzing}
            title="Detect the climber's body in each frame and compute movement scores."
            className={`flex-1 py-3 rounded-xl text-sm font-medium transition-all ${
              store.isAnalyzing
                ? "bg-accent/10 text-accent border border-accent/30"
                : videoId && !hasAnalysis
                  ? "bg-accent text-white shadow-md hover:shadow-lg hover:bg-accent-hover pulse-border"
                  : "bg-bg-card-solid text-text border border-border hover:border-accent/40"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {store.isAnalyzing ? "analyzing..." : hasAnalysis ? "re-analyze" : "analyze"}
          </button>
          <button
            onClick={handleRender}
            disabled={!videoId || !hasAnalysis || store.isRendering}
            title="Render the speed-ramped video with your current settings."
            className={`flex-1 py-3 rounded-xl text-sm font-medium transition-all ${
              store.isRendering
                ? "bg-warm/10 text-warm border border-warm/30"
                : hasAnalysis
                  ? "bg-accent text-white shadow-md hover:shadow-lg hover:bg-accent-hover"
                  : "bg-bg-card-solid text-text-muted border border-border"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {store.isRendering ? "rendering..." : "render"}
          </button>
        </div>
        <ProgressBar />
      </div>

      {/* Timeline */}
      <TimelineEditor />

      {/* Stats */}
      {store.stats && (
        <div className="flex flex-wrap gap-2 justify-center">
          {[
            { label: "output", value: `${store.stats.output_duration}s` },
            { label: "speed", value: `${store.stats.speed_min}x\u2013${store.stats.speed_max}x` },
            { label: "ratio", value: `${store.stats.action_rest_ratio}x` },
            { label: "real-time", value: `${store.stats.slow_pct}%` },
          ].map(({ label, value }) => (
            <span key={label} className="px-3 py-1 bg-bg-card-solid border border-border rounded-full text-xs font-mono text-text-muted">
              {label}: <span className="text-text font-medium">{value}</span>
            </span>
          ))}
        </div>
      )}

      {/* Analysis feature badges */}
      {analysis && (
        <div className="flex flex-wrap gap-1.5 justify-center -mt-4">
          {analysis.tracker_available && (
            <span className="px-2 py-0.5 bg-accent/10 border border-accent/20 rounded-full text-[10px] font-medium text-accent">
              person tracking
            </span>
          )}
          {analysis.flow_available && (
            <span className="px-2 py-0.5 bg-accent/10 border border-accent/20 rounded-full text-[10px] font-medium text-accent">
              optical flow
            </span>
          )}
        </div>
      )}

      {/* Settings */}
      <SettingsPanel />

      {/* Footer */}
      <footer className="text-center text-xs text-text-muted py-6 opacity-40">
        made for sending
      </footer>
    </main>
  );
}
