"use client";

import { useCallback, useEffect, useRef } from "react";
import { useStore } from "@/lib/store";
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

  // Auto-solve curve on any settings/pin change (debounced)
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
    store.setAnalyzing(true);
    store.setProgress(0, "Starting analysis...");
    try {
      const result = await analyzeVideo(videoId, 2, false, (p, msg) => {
        store.setProgress(p, msg);
      });
      if (result) {
        store.setAnalysis(result);
        store.setProgress(0.95, "Computing speed curve...");
        const solveResult = await solveCurve(videoId, settings, pins);
        store.setCurve(solveResult.curve, solveResult.times, solveResult.stats);
        store.setProgress(0, "Analysis complete!");
      }
    } catch (e: any) {
      store.setProgress(0, `Error: ${e.message}`);
    } finally {
      store.setAnalyzing(false);
    }
  }, [videoId, settings, pins]);

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
    } catch (e: any) {
      store.setProgress(0, `Error: ${e.message}`);
    } finally {
      store.setRendering(false);
    }
  }, [videoId, settings, pins]);

  const hasAnalysis = !!analysis;

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 flex flex-col gap-6">
      {/* Header */}
      <header className="flex items-baseline gap-3">
        <h1 className="text-3xl font-black tracking-tight" style={{ color: "var(--accent)" }}>
          climb-ramp
        </h1>
        <p className="text-sm text-text-muted">
          speed-ramp your sends
        </p>
      </header>

      {/* Video I/O */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <VideoUpload />
        <VideoPlayer />
      </div>

      {/* Action bar */}
      <div className="flex flex-col gap-3">
        <div className="flex gap-3">
          <button
            onClick={handleAnalyze}
            disabled={!videoId || store.isAnalyzing}
            title="Detect the climber's body in each frame and compute movement scores. Only needed once per video — results are cached."
            className={`flex-1 py-3.5 rounded-xl font-bold text-sm border-2 transition-all ${
              store.isAnalyzing
                ? "border-accent bg-accent/10 text-accent animate-pulse"
                : videoId && !hasAnalysis
                  ? "border-accent bg-accent text-white shadow-lg pulse-border"
                  : "border-border bg-bg-card text-text hover:border-accent hover:bg-bg-input"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {store.isAnalyzing ? "🔍 analyzing..." : hasAnalysis ? "🔄 re-analyze" : "🔍 analyze"}
          </button>
          <button
            onClick={handleRender}
            disabled={!videoId || !hasAnalysis || store.isRendering}
            title="Render the speed-ramped video with your current settings. Tweak sliders and pins first, then hit render when you're happy with the curve."
            className={`flex-1 py-3.5 rounded-xl font-bold text-sm border-2 transition-all ${
              store.isRendering
                ? "border-warm bg-warm/10 text-warm animate-pulse"
                : hasAnalysis
                  ? "border-accent bg-accent text-white shadow-lg hover:bg-accent-hover"
                  : "border-border bg-bg-card text-text-muted"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {store.isRendering ? "🎬 rendering..." : "🎬 render"}
          </button>
        </div>
        <ProgressBar />
      </div>

      {/* Timeline editor */}
      <TimelineEditor />

      {/* Stats pill */}
      {store.stats && (
        <div className="flex flex-wrap gap-2 justify-center">
          {[
            { label: "output", value: `${store.stats.output_duration}s`, emoji: "⏱" },
            { label: "speed", value: `${store.stats.speed_min}x–${store.stats.speed_max}x`, emoji: "⚡" },
            { label: "ratio", value: `${store.stats.action_rest_ratio}x`, emoji: "📊" },
            { label: "real-time", value: `${store.stats.slow_pct}%`, emoji: "🐌" },
          ].map(({ label, value, emoji }) => (
            <span key={label} className="px-3 py-1 bg-bg-card border border-border rounded-full text-xs font-mono text-text-muted">
              {emoji} {label}: <span className="text-text font-semibold">{value}</span>
            </span>
          ))}
        </div>
      )}

      {/* Settings */}
      <SettingsPanel />

      {/* Footer */}
      <footer className="text-center text-xs text-text-muted py-4 opacity-60">
        made for sending
      </footer>
    </main>
  );
}
