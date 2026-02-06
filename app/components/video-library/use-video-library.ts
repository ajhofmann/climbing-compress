"use client";

import { useCallback, useEffect, useState } from "react";
import { listVideos } from "@/lib/api";
import { useStore } from "@/lib/store";
import { VideoInfo } from "@/lib/types";

interface VideoRecord {
  video_id: string;
  filename: string;
  info: VideoInfo;
  project_id?: string | null;
  project_name?: string | null;
  created_at?: number;
  size_bytes?: number;
  cached?: boolean;
}

export function useVideoLibrary() {
  const { selectedProjectId, videoId, setVideo, setProgress, setSelectedProjectId } = useStore();
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listVideos(selectedProjectId ?? "unassigned");
      setVideos(data ?? []);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load videos";
      setError(msg);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 6000);
    return () => window.clearInterval(id);
  }, [refresh, videoId]);

  const loadVideo = useCallback((video: VideoRecord) => {
    setVideo(video.video_id, video.info, []);
    const nextProjectId = video.project_id ?? null;
    setSelectedProjectId(nextProjectId);
    if (typeof window !== "undefined") {
      if (nextProjectId) {
        window.localStorage.setItem("projectId", nextProjectId);
      } else {
        window.localStorage.setItem("projectId", "unassigned");
      }
    }
    setProgress(0, `Loaded ${video.filename}`);
  }, [setVideo, setProgress, setSelectedProjectId]);

  return { videos, error, refresh, loadVideo };
}
