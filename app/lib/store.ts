"use client";

import { create } from "zustand";
import { Pin, Settings, CurveStats, AnalysisData, VideoInfo, DEFAULT_SETTINGS } from "./types";

export interface AnalysisParams {
  stride: number;
  useTracker: boolean;
  useFlow: boolean;
}

interface Store {
  // Video
  videoId: string | null;
  videoInfo: VideoInfo | null;
  thumbnails: string[];
  setVideo: (id: string, info: VideoInfo, thumbs: string[]) => void;

  // Analysis
  analysis: AnalysisData | null;
  analysisParams: AnalysisParams | null;
  setAnalysis: (data: AnalysisData, params: AnalysisParams) => void;

  // Speed curve
  curve: number[];
  curveTimes: number[];
  stats: CurveStats | null;
  setCurve: (curve: number[], times: number[], stats: CurveStats) => void;

  // Pins
  pins: Pin[];
  setPins: (pins: Pin[]) => void;
  addPin: (pin: Pin) => void;
  removePin: (index: number) => void;
  updatePin: (index: number, pin: Pin) => void;

  // Settings
  settings: Settings;
  updateSettings: (partial: Partial<Settings>) => void;

  // Output
  outputId: string | null;
  setOutputId: (id: string | null) => void;

  // Progress
  isAnalyzing: boolean;
  isRendering: boolean;
  progress: number;
  progressMessage: string;
  setAnalyzing: (v: boolean) => void;
  setRendering: (v: boolean) => void;
  setProgress: (p: number, msg: string) => void;
}

export const useStore = create<Store>((set) => ({
  videoId: null,
  videoInfo: null,
  thumbnails: [],
  setVideo: (id, info, thumbs) => set((s) => ({ videoId: id, videoInfo: info, thumbnails: thumbs, analysis: null, analysisParams: null, curve: [], curveTimes: [], stats: null, outputId: null, pins: [], settings: { ...s.settings, trimStart: 0, trimEnd: 0 } })),

  analysis: null,
  analysisParams: null,
  setAnalysis: (data, params) => set({ analysis: data, analysisParams: params }),

  curve: [],
  curveTimes: [],
  stats: null,
  setCurve: (curve, times, stats) => set({ curve, curveTimes: times, stats }),

  pins: [],
  setPins: (pins) => set({ pins }),
  addPin: (pin) => set((s) => ({ pins: [...s.pins, pin] })),
  removePin: (i) => set((s) => ({ pins: s.pins.filter((_, j) => j !== i) })),
  updatePin: (i, pin) => set((s) => ({ pins: s.pins.map((p, j) => j === i ? pin : p) })),

  settings: { ...DEFAULT_SETTINGS },
  updateSettings: (partial) => set((s) => ({ settings: { ...s.settings, ...partial } })),

  outputId: null,
  setOutputId: (id) => set({ outputId: id }),

  isAnalyzing: false,
  isRendering: false,
  progress: 0,
  progressMessage: "",
  setAnalyzing: (v) => set({ isAnalyzing: v }),
  setRendering: (v) => set({ isRendering: v }),
  setProgress: (p, msg) => set({ progress: p, progressMessage: msg }),
}));
