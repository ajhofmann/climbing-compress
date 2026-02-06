"use client";

import { useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { listOutputs } from "@/lib/api";

interface OutputRecord {
  id: string;
  video_id: string;
  video_filename?: string | null;
  project_id?: string | null;
  project_name?: string | null;
  job_id: string;
  output_type: string;
  path: string;
  created_at?: number;
  output_duration?: number | null;
}

export function useOutputHistory() {
  const {
    videoId,
    selectedProjectId,
    setOutputId,
    setPreviewId,
    setComparisonId,
    setProgress,
    setSelectedProjectId,
  } = useStore();
  const [outputs, setOutputs] = useState<OutputRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const projectFilter = videoId ? null : (selectedProjectId ?? "unassigned");
      const data = await listOutputs(videoId, projectFilter);
      setOutputs(data ?? []);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load outputs";
      setError(msg);
    }
  }, [videoId, selectedProjectId]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 6000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const loadOutput = useCallback((output: OutputRecord) => {
    const nextProjectId = output.project_id ?? null;
    setSelectedProjectId(nextProjectId);
    if (typeof window !== "undefined") {
      if (nextProjectId) {
        window.localStorage.setItem("projectId", nextProjectId);
      } else {
        window.localStorage.setItem("projectId", "unassigned");
      }
    }
    if (output.output_type === "preview") {
      setPreviewId(output.id);
      setProgress(0, "Loaded preview output");
    } else if (output.output_type === "comparison") {
      setComparisonId(output.id);
      setProgress(0, "Loaded comparison output");
    } else {
      setOutputId(output.id);
      setProgress(0, "Loaded output");
    }
  }, [setOutputId, setPreviewId, setComparisonId, setProgress, setSelectedProjectId]);

  return { outputs, error, refresh, loadOutput };
}
