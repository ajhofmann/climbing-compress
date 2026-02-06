"use client";

import { useVideoLibrary } from "./use-video-library";
import { styles } from "./styles";

const formatAge = (timestamp?: number) => {
  if (!timestamp) return "";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
};

export function VideoLibrary() {
  const { videos, error, refresh, loadVideo } = useVideoLibrary();

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-cyan)" }}>video library</span>
        <button className={styles.button} onClick={refresh}>Refresh</button>
      </div>

      {error && <span className={styles.empty} style={{ color: "var(--danger)" }}>{error}</span>}

      {videos.length === 0 ? (
        <span className={styles.empty}>No videos yet.</span>
      ) : (
        <div className={styles.list}>
          {videos.slice(0, 5).map((video) => (
            <div key={video.video_id} className={styles.row}>
              <span className="text-text">{video.filename}</span>
              {video.created_at && (
                <span className={styles.meta}>{formatAge(video.created_at)}</span>
              )}
              <span className={styles.meta}>{Math.round(video.info.duration)}s</span>
              <span className={styles.meta}>{video.info.width}x{video.info.height}</span>
              <span className={styles.meta}>{video.project_name ?? "unassigned"}</span>
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
