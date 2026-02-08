"use client";

import { create } from "zustand";
import { Pin, Keyframe, Settings, CurveStats, AnalysisData, VideoInfo, DEFAULT_SETTINGS, CruxPoint } from "./types";

export interface AnalysisParams {
  stride: number;
  useTracker: boolean;
  useFlow: boolean;
}

interface Store {
  // Video
  videoId: string | null;
  videoName: string | null;
  videoInfo: VideoInfo | null;
  thumbnails: string[];
  setVideo: (id: string, info: VideoInfo, thumbs: string[], name?: string) => void;
  setVideoName: (name: string | null) => void;
  clearVideo: () => void;

  // Analysis
  analysis: AnalysisData | null;
  analysisParams: AnalysisParams | null;
  setAnalysis: (data: AnalysisData, params: AnalysisParams) => void;

  // Speed curve
  curve: number[];
  curveTimes: number[];
  solveScores: number[];
  restRegions: [number, number][];
  cruxPoints: CruxPoint[];
  stats: CurveStats | null;
  setCurve: (
    curve: number[],
    times: number[],
    stats: CurveStats,
    scores?: number[],
    restRegions?: [number, number][],
    cruxPoints?: CruxPoint[],
  ) => void;

  // Pins
  pins: Pin[];
  setPins: (pins: Pin[]) => void;
  addPin: (pin: Pin) => void;
  removePin: (index: number) => void;
  updatePin: (index: number, pin: Pin) => void;
  keyframes: Keyframe[];
  setKeyframes: (keyframes: Keyframe[]) => void;
  addKeyframe: (keyframe: Keyframe) => void;
  removeKeyframe: (index: number) => void;
  updateKeyframe: (index: number, keyframe: Keyframe) => void;

  // Settings
  settings: Settings;
  updateSettings: (partial: Partial<Settings>) => void;

  // Output
  outputId: string | null;
  comparisonId: string | null;
  setOutputId: (id: string | null) => void;
  setComparisonId: (id: string | null) => void;

  // Playback
  playbackTime: number;
  setPlaybackTime: (t: number) => void;

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
  videoName: null,
  videoInfo: null,
  thumbnails: [],
  setVideo: (id, info, thumbs, name) => set((s) => ({ videoId: id, videoName: name ?? null, videoInfo: info, thumbnails: thumbs, analysis: null, analysisParams: null, curve: [], curveTimes: [], solveScores: [], restRegions: [], cruxPoints: [], stats: null, outputId: null, comparisonId: null, pins: [], keyframes: [], settings: { ...s.settings, trimStart: 0, trimEnd: 0, editMode: "pins" } })),
  setVideoName: (name) => set({ videoName: name }),
  clearVideo: () => set((s) => ({
    videoId: null,
    videoName: null,
    videoInfo: null,
    thumbnails: [],
    analysis: null,
    analysisParams: null,
    curve: [],
    curveTimes: [],
    solveScores: [],
    restRegions: [],
    cruxPoints: [],
    stats: null,
    outputId: null,
    comparisonId: null,
    pins: [],
    keyframes: [],
    playbackTime: 0,
    settings: { ...s.settings, trimStart: 0, trimEnd: 0, editMode: "pins" },
  })),

  analysis: null,
  analysisParams: null,
  setAnalysis: (data, params) => set({ analysis: data, analysisParams: params }),

  curve: [],
  curveTimes: [],
  solveScores: [],
  restRegions: [],
  cruxPoints: [],
  stats: null,
  setCurve: (curve, times, stats, scores, restRegions, cruxPoints) => set({
    curve, curveTimes: times, stats,
    solveScores: scores ?? [],
    restRegions: restRegions ?? [],
    cruxPoints: cruxPoints ?? [],
  }),

  pins: [],
  setPins: (pins) => set({ pins }),
  addPin: (pin) => set((s) => ({ pins: [...s.pins, pin] })),
  removePin: (i) => set((s) => ({ pins: s.pins.filter((_, j) => j !== i) })),
  updatePin: (i, pin) => set((s) => ({ pins: s.pins.map((p, j) => j === i ? pin : p) })),
  keyframes: [],
  setKeyframes: (keyframes) => set({ keyframes: [...keyframes].sort((a, b) => a.time - b.time) }),
  addKeyframe: (keyframe) => set((s) => ({ keyframes: [...s.keyframes, keyframe].sort((a, b) => a.time - b.time) })),
  removeKeyframe: (i) => set((s) => ({ keyframes: s.keyframes.filter((_, j) => j !== i) })),
  updateKeyframe: (i, keyframe) => set((s) => ({
    keyframes: s.keyframes.map((k, j) => (j === i ? keyframe : k)).sort((a, b) => a.time - b.time),
  })),

  settings: { ...DEFAULT_SETTINGS },
  updateSettings: (partial) => set((s) => ({ settings: { ...s.settings, ...partial } })),

  outputId: null,
  comparisonId: null,
  setOutputId: (id) => set({ outputId: id }),
  setComparisonId: (id) => set({ comparisonId: id }),

  playbackTime: 0,
  setPlaybackTime: (t) => set({ playbackTime: t }),

  isAnalyzing: false,
  isRendering: false,
  progress: 0,
  progressMessage: "",
  setAnalyzing: (v) => set({ isAnalyzing: v }),
  setRendering: (v) => set({ isRendering: v }),
  setProgress: (p, msg) => set({ progress: p, progressMessage: msg }),
}));
