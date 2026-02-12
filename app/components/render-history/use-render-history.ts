"use client";

import { useCallback, useEffect, useState } from "react";
import { listRenderHistory, RenderHistoryItem } from "@/lib/api";

export function useRenderHistory(videoId: string | null) {
  const [entries, setEntries] = useState<RenderHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!videoId) {
      setEntries([]);
      setError(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const rows = await listRenderHistory(videoId);
      setEntries(rows);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load render history";
      setEntries([]);
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    entries,
    isLoading,
    error,
    refresh,
  };
}

