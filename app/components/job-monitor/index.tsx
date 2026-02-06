"use client";

import { useJobMonitor } from "./use-job-monitor";
import { styles } from "./styles";
import { useStore } from "@/lib/store";

const STATUS_COLORS: Record<string, string> = {
  queued: "var(--neon-cyan)",
  running: "var(--neon-lime)",
  success: "var(--neon-cyan)",
  failed: "var(--danger)",
  cancelled: "var(--neon-magenta)",
};

function formatJobType(jobType: string) {
  return jobType.replace(/_/g, " ");
}

function formatAge(timestamp?: number) {
  if (!timestamp) return "";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

function formatDurationSeconds(duration?: number | null) {
  if (duration === null || duration === undefined) return "";
  const seconds = Math.max(0, Math.floor(duration));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

export function JobMonitor() {
  const { jobs, error, refresh, cancel, isCancelling, retry, isRetrying } = useJobMonitor();
  const { videoId } = useStore();

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-orange)" }}>job monitor</span>
        <div className="flex items-center gap-2">
          {error && <span className="text-[10px] text-danger">{error}</span>}
          <button className={styles.button} onClick={refresh}>Refresh</button>
        </div>
      </div>

      {jobs.length === 0 ? (
        <span className={styles.empty}>No jobs yet.</span>
      ) : (
        <div className={styles.list}>
          {jobs.map((job) => (
            <div
              key={job.id}
              className={`${styles.row} ${job.video_id === videoId ? styles.rowActive : ""}`}
            >
              {(() => {
                const isDone = job.status === "success" || job.status === "failed" || job.status === "cancelled";
                const durationSeconds = job.duration ?? (
                  job.updated_at && job.created_at ? job.updated_at - job.created_at : null
                );
                const timeLabel = isDone
                  ? formatDurationSeconds(durationSeconds)
                  : formatAge(job.created_at);
                const timePrefix = isDone ? "dur " : "";
                return (
                  <>
              <span className={styles.badge} style={{ background: "#080810", color: STATUS_COLORS[job.status] ?? "var(--text)" }}>
                {job.status}
              </span>
              <span className="uppercase text-text-muted">{formatJobType(job.job_type)}</span>
              <span className="font-mono text-text">{Math.round((job.progress ?? 0) * 100)}%</span>
              {timeLabel && (
                <span className="text-text-muted">{timePrefix}{timeLabel}</span>
              )}
              {job.message && (
                <span className="text-text-muted truncate max-w-[160px]" title={job.message}>{job.message}</span>
              )}
              <span className="text-text-muted" title={job.project_name ?? "unassigned"}>
                {job.project_name ?? "unassigned"}
              </span>
              <span className="ml-auto text-text-muted" title={job.video_filename ?? job.video_id}>
                {job.video_filename ?? job.video_id}
              </span>
              {(job.status === "queued" || job.status === "running") && (
                <button
                  onClick={() => cancel(job.id)}
                  disabled={isCancelling === job.id}
                  className="text-[9px] font-pixel uppercase text-neon-magenta hover:text-white"
                >
                  {isCancelling === job.id ? "CANCEL..." : "CANCEL"}
                </button>
              )}
              {(job.status === "failed" || job.status === "cancelled") && (
                <button
                  onClick={() => retry(job.id)}
                  disabled={isRetrying === job.id}
                  className="text-[9px] font-pixel uppercase text-neon-cyan hover:text-white"
                >
                  {isRetrying === job.id ? "RETRY..." : "RETRY"}
                </button>
              )}
                  </>
                );
              })()}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
