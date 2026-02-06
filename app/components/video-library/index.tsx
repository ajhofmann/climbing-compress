"use client";

import { useVideoLibrary } from "./use-video-library";
import { styles } from "./styles";

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
              <span className={styles.meta}>{Math.round(video.info.duration)}s</span>
              <span className={styles.meta}>{video.info.width}x{video.info.height}</span>
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
