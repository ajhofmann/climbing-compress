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

export function JobMonitor() {
  const { jobs, error } = useJobMonitor();

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
              <span className={styles.badge} style={{ background: "#080810", color: STATUS_COLORS[job.status] ?? "var(--text)" }}>
                {job.status}
              </span>
              <span className="uppercase text-text-muted">{formatJobType(job.job_type)}</span>
              <span className="font-mono text-text">{Math.round((job.progress ?? 0) * 100)}%</span>
              <span className="ml-auto text-text-muted">{job.video_id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
