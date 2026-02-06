"use client";

import { useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { listOutputs } from "@/lib/api";

interface OutputRecord {
  id: string;
  video_id: string;
  job_id: string;
  output_type: string;
  path: string;
  created_at?: number;
}

export function useOutputHistory() {
  const { videoId, selectedProjectId, setOutputId, setPreviewId, setComparisonId, setProgress } = useStore();
  const [outputs, setOutputs] = useState<OutputRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      if (!videoId && !selectedProjectId) {
        setOutputs([]);
        return;
      }
      const data = await listOutputs(videoId, selectedProjectId);
      setOutputs(data ?? []);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load outputs";
      setError(msg);
    }
  }, [videoId, selectedProjectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const loadOutput = useCallback((output: OutputRecord) => {
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
  }, [setOutputId, setPreviewId, setComparisonId, setProgress]);

  return { outputs, error, refresh, loadOutput };
}
