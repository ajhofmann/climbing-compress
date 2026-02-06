"use client";

import { useSystemMetrics } from "./use-system-metrics";
import { styles } from "./styles";

function formatLabel(label: string) {
  return label.replace(/_/g, " ");
}

function formatOutputType(label: string) {
  if (label === "main") return "render";
  if (label === "comparison") return "compare";
  return formatLabel(label);
}

export function SystemMetrics() {
  const { metrics, error } = useSystemMetrics();

  const jobStatuses = metrics?.jobs_by_status ?? {};
  const jobTypes = metrics?.jobs_by_type ?? {};
  const outputTypes = metrics?.outputs_by_type ?? {};
  const avgDurations = metrics?.avg_duration_by_type ?? {};

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-lime)" }}>system metrics</span>
        {error && <span className="text-[10px] text-danger">{error}</span>}
      </div>

      <div className={styles.grid}>
        {[
          { label: "videos", value: metrics?.videos ?? 0 },
          { label: "outputs", value: metrics?.outputs ?? 0 },
          { label: "projects", value: metrics?.projects ?? 0 },
          { label: "jobs", value: Object.values(jobStatuses).reduce((sum, v) => sum + v, 0) },
        ].map((item) => (
          <div key={item.label} className={styles.card} style={{ background: "#080810" }}>
            <div className={styles.label}>{item.label}</div>
            <div className={styles.value}>{item.value}</div>
          </div>
        ))}
      </div>

      <div className={styles.list}>
        {Object.entries(jobStatuses).map(([status, count]) => (
          <div key={status} className={styles.pill} style={{ background: "#080810" }}>
            <span>{formatLabel(status)}</span>
            <span className="font-mono text-text">{count}</span>
          </div>
        ))}
      </div>

      <div className={styles.list}>
        {Object.entries(jobTypes).map(([type, count]) => (
          <div key={type} className={styles.pill} style={{ background: "#080810" }}>
            <span>{formatLabel(type)}</span>
            <span className="font-mono text-text">{count}</span>
          </div>
        ))}
      </div>

      {Object.keys(outputTypes).length > 0 && (
        <div className={styles.list}>
          {Object.entries(outputTypes).map(([type, count]) => (
            <div key={type} className={styles.pill} style={{ background: "#080810" }}>
              <span>out {formatOutputType(type)}</span>
              <span className="font-mono text-text">{count}</span>
            </div>
          ))}
        </div>
      )}

      {Object.keys(avgDurations).length > 0 && (
        <div className={styles.list}>
          {Object.entries(avgDurations).map(([type, duration]) => (
            <div key={type} className={styles.pill} style={{ background: "#080810" }}>
              <span>{formatLabel(type)} avg</span>
              <span className="font-mono text-text">{duration}s</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
