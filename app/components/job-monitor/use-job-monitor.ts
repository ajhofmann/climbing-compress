"use client";

import { useCallback, useEffect, useState } from "react";
import { listJobs } from "@/lib/api";
import { JobRecord } from "@/lib/types";

export function useJobMonitor() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data.slice(0, 6));
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load jobs";
      setError(msg);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 6000);
    return () => window.clearInterval(id);
  }, [refresh]);

  return { jobs, error };
}
