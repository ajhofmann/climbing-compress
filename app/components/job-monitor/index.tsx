"use client";

import { useJobMonitor } from "./use-job-monitor";
import { styles } from "./styles";

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

function formatDuration(start?: number, end?: number) {
  if (!start || !end) return "";
  const seconds = Math.max(0, Math.floor(end - start));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

export function JobMonitor() {
  const { jobs, error, cancel, isCancelling, retry, isRetrying } = useJobMonitor();

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-orange)" }}>job monitor</span>
        {error && <span className="text-[10px] text-danger">{error}</span>}
      </div>

      {jobs.length === 0 ? (
        <span className={styles.empty}>No jobs yet.</span>
      ) : (
        <div className={styles.list}>
          {jobs.map((job) => (
            <div key={job.id} className={styles.row}>
              {(() => {
                const isDone = job.status === "success" || job.status === "failed" || job.status === "cancelled";
                const timeLabel = isDone
                  ? formatDuration(job.created_at, job.updated_at)
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
                <span className="text-text-muted truncate max-w-[160px]">{job.message}</span>
              )}
              <span className="text-text-muted">{job.project_name ?? "unassigned"}</span>
              <span className="ml-auto text-text-muted">{job.video_filename ?? job.video_id}</span>
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
