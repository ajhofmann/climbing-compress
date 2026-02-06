"use client";

import { create } from "zustand";
import { Pin, Settings, CurveStats, AnalysisData, VideoInfo, DEFAULT_SETTINGS, Project } from "./types";

export interface AnalysisParams {
  stride: number;
  useTracker: boolean;
  useFlow: boolean;
  climberStrategy: string;
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
  solveScores: number[];
  restRegions: [number, number][];
  stats: CurveStats | null;
  setCurve: (curve: number[], times: number[], stats: CurveStats, scores?: number[], restRegions?: [number, number][]) => void;

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
  comparisonId: string | null;
  setOutputId: (id: string | null) => void;
  setComparisonId: (id: string | null) => void;
  previewId: string | null;
  setPreviewId: (id: string | null) => void;

  // Projects
  projects: Project[];
  selectedProjectId: string | null;
  setProjects: (projects: Project[]) => void;
  addProject: (project: Project) => void;
  setSelectedProjectId: (id: string | null) => void;

  // Playback
  playbackTime: number;
  setPlaybackTime: (t: number) => void;

  // Progress
  isAnalyzing: boolean;
  isRendering: boolean;
  isPreviewing: boolean;
  progress: number;
  progressMessage: string;
  setAnalyzing: (v: boolean) => void;
  setRendering: (v: boolean) => void;
  setPreviewing: (v: boolean) => void;
  setProgress: (p: number, msg: string) => void;
}

const getInitialFlag = (key: string, fallback: boolean) => {
  if (typeof window === "undefined") return fallback;
  const stored = window.localStorage.getItem(key);
  if (stored === "true") return true;
  if (stored === "false") return false;
  return fallback;
};

export const useStore = create<Store>((set) => ({
  videoId: null,
  videoInfo: null,
  thumbnails: [],
  setVideo: (id, info, thumbs) => set((s) => ({ videoId: id, videoInfo: info, thumbnails: thumbs, analysis: null, analysisParams: null, curve: [], curveTimes: [], solveScores: [], restRegions: [], stats: null, outputId: null, comparisonId: null, previewId: null, pins: [], settings: { ...s.settings, trimStart: 0, trimEnd: 0 } })),

  analysis: null,
  analysisParams: null,
  setAnalysis: (data, params) => set({ analysis: data, analysisParams: params }),

  curve: [],
  curveTimes: [],
  solveScores: [],
  restRegions: [],
  stats: null,
  setCurve: (curve, times, stats, scores, restRegions) => set({
    curve, curveTimes: times, stats,
    solveScores: scores ?? [],
    restRegions: restRegions ?? [],
  }),

  pins: [],
  setPins: (pins) => set({ pins }),
  addPin: (pin) => set((s) => ({ pins: [...s.pins, pin] })),
  removePin: (i) => set((s) => ({ pins: s.pins.filter((_, j) => j !== i) })),
  updatePin: (i, pin) => set((s) => ({ pins: s.pins.map((p, j) => j === i ? pin : p) })),

  settings: {
    ...DEFAULT_SETTINGS,
    queueMode: getInitialFlag("queueMode", DEFAULT_SETTINGS.queueMode),
    autoPreview: getInitialFlag("autoPreview", DEFAULT_SETTINGS.autoPreview),
  },
  updateSettings: (partial) => set((s) => {
    const next = { ...s.settings, ...partial };
    if (partial.queueMode !== undefined && typeof window !== "undefined") {
      window.localStorage.setItem("queueMode", String(partial.queueMode));
    }
    if (partial.autoPreview !== undefined && typeof window !== "undefined") {
      window.localStorage.setItem("autoPreview", String(partial.autoPreview));
    }
    return { settings: next };
  }),

  outputId: null,
  comparisonId: null,
  setOutputId: (id) => set({ outputId: id }),
  setComparisonId: (id) => set({ comparisonId: id }),
  previewId: null,
  setPreviewId: (id) => set({ previewId: id }),

  projects: [],
  selectedProjectId: null,
  setProjects: (projects) => set({ projects }),
  addProject: (project) => set((s) => ({ projects: [project, ...s.projects] })),
  setSelectedProjectId: (id) => set({ selectedProjectId: id }),

  playbackTime: 0,
  setPlaybackTime: (t) => set({ playbackTime: t }),

  isAnalyzing: false,
  isRendering: false,
  isPreviewing: false,
  progress: 0,
  progressMessage: "",
  setAnalyzing: (v) => set({ isAnalyzing: v }),
  setRendering: (v) => set({ isRendering: v }),
  setPreviewing: (v) => set({ isPreviewing: v }),
  setProgress: (p, msg) => set({ progress: p, progressMessage: msg }),
}));
