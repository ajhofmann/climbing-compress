"use client";

import { useCallback, useEffect, useState } from "react";
import { cancelJob, listJobs, retryJob } from "@/lib/api";
import { JobRecord } from "@/lib/types";
import { useStore } from "@/lib/store";

export function useJobMonitor() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState<string | null>(null);
  const { selectedProjectId } = useStore();
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listJobs(selectedProjectId ?? "unassigned");
      setJobs(data.slice(0, 10));
      setError(null);
      setLastUpdated(Date.now());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load jobs";
      setError(msg);
    }
  }, [selectedProjectId]);

  const cancel = useCallback(async (jobId: string) => {
    setIsCancelling(jobId);
    try {
      await cancelJob(jobId);
      await refresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel job";
      setError(msg);
    } finally {
      setIsCancelling(null);
    }
  }, [refresh]);

  const retry = useCallback(async (jobId: string) => {
    setIsRetrying(jobId);
    try {
      await retryJob(jobId);
      await refresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retry job";
      setError(msg);
    } finally {
      setIsRetrying(null);
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 6000);
    return () => window.clearInterval(id);
  }, [refresh]);

  return { jobs, error, refresh, cancel, isCancelling, retry, isRetrying, lastUpdated };
}
