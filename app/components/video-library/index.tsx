"use client";

import { useVideoLibrary } from "./use-video-library";
import { styles } from "./styles";
import { useStore } from "@/lib/store";

const formatAge = (timestamp?: number) => {
  if (!timestamp) return "";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
};

const formatBytes = (size?: number) => {
  if (size === undefined) return "";
  if (size === 0) return "0kb";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)}kb`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)}mb`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)}gb`;
};

export function VideoLibrary() {
  const { videos, error, refresh, loadVideo, lastUpdated } = useVideoLibrary();
  const { videoId } = useStore();

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-cyan)" }}>video library</span>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-[10px] text-text-muted">
              {new Date(lastUpdated).toLocaleTimeString()}
            </span>
          )}
          <button className={styles.button} onClick={refresh}>Refresh</button>
        </div>
      </div>

      {error && <span className={styles.empty} style={{ color: "var(--danger)" }}>{error}</span>}

      {videos.length === 0 ? (
        <span className={styles.empty}>No videos yet.</span>
      ) : (
        <div className={styles.list}>
          {videos.slice(0, 5).map((video) => (
            <div
              key={video.video_id}
              className={`${styles.row} ${video.video_id === videoId ? styles.rowActive : ""}`}
            >
              <span className="text-text" title={video.filename}>{video.filename}</span>
              {video.created_at && (
                <span className={styles.meta}>{formatAge(video.created_at)}</span>
              )}
              <span className={styles.meta}>{Math.round(video.info.duration)}s</span>
              {video.size_bytes !== undefined && (
                <span className={styles.meta}>{formatBytes(video.size_bytes)}</span>
              )}
              <span className={styles.meta}>{video.info.width}x{video.info.height}</span>
              <span className={styles.meta} title={video.project_name ?? "unassigned"}>
                {video.project_name ?? "unassigned"}
              </span>
              {video.cached && <span className={styles.meta}>cached</span>}
              <button className={styles.button} onClick={() => loadVideo(video)}>
                Load
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
