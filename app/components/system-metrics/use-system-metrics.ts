"use client";

import { useCallback, useEffect, useState } from "react";
import { getMetrics } from "@/lib/api";
import { Metrics } from "@/lib/types";

export function useSystemMetrics() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getMetrics();
      setMetrics(data);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load metrics";
      setError(msg);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 8000);
    return () => window.clearInterval(id);
  }, [refresh]);

  return { metrics, error, refresh };
}
