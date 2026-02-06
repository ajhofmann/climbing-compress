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
  const { videoId, setOutputId, setPreviewId, setComparisonId, setProgress } = useStore();
  const [outputs, setOutputs] = useState<OutputRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!videoId) {
      setOutputs([]);
      return;
    }
    try {
      const data = await listOutputs(videoId);
      setOutputs(data ?? []);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load outputs";
      setError(msg);
    }
  }, [videoId]);

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
