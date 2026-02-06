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

function formatBytes(size?: number) {
  if (!size) return "0kb";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)}kb`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)}mb`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)}gb`;
}

function formatSeconds(value?: number) {
  if (value === null || value === undefined) return "";
  const formatted = value < 10 ? value.toFixed(1) : value.toFixed(0);
  return `${formatted.replace(/\.0$/, "")}s`;
}

export function SystemMetrics() {
  const { metrics, error, refresh, lastUpdated } = useSystemMetrics();

  const jobStatuses = metrics?.jobs_by_status ?? {};
  const jobTypes = metrics?.jobs_by_type ?? {};
  const outputTypes = metrics?.outputs_by_type ?? {};
  const avgOutputDurations = metrics?.avg_output_duration_by_type ?? {};
  const avgDurations = metrics?.avg_duration_by_type ?? {};

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-lime)" }}>system metrics</span>
        <div className="flex items-center gap-2">
          {error && <span className="text-[10px] text-danger">{error}</span>}
          {lastUpdated && (
            <span className="text-[10px] text-text-muted">
              {new Date(lastUpdated).toLocaleTimeString()}
            </span>
          )}
          <button className={styles.button} onClick={refresh}>Refresh</button>
        </div>
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

      {Object.keys(avgOutputDurations).length > 0 && (
        <div className={styles.list}>
          {Object.entries(avgOutputDurations).map(([type, duration]) => (
            <div key={type} className={styles.pill} style={{ background: "#080810" }}>
              <span>out {formatOutputType(type)} avg</span>
              <span className="font-mono text-text">{formatSeconds(duration)}</span>
            </div>
          ))}
        </div>
      )}

      {Object.keys(avgDurations).length > 0 && (
        <div className={styles.list}>
          {Object.entries(avgDurations).map(([type, duration]) => (
            <div key={type} className={styles.pill} style={{ background: "#080810" }}>
              <span>{formatLabel(type)} avg</span>
              <span className="font-mono text-text">{formatSeconds(duration)}</span>
            </div>
          ))}
        </div>
      )}

      {metrics && (
        <div className={styles.list}>
          <div className={styles.pill} style={{ background: "#080810" }}>
            <span>db size</span>
            <span className="font-mono text-text">{formatBytes(metrics.db_size_bytes)}</span>
          </div>
          <div className={styles.pill} style={{ background: "#080810" }}>
            <span>input storage</span>
            <span className="font-mono text-text">{formatBytes(metrics.input_storage_bytes)}</span>
          </div>
          <div className={styles.pill} style={{ background: "#080810" }}>
            <span>cache storage</span>
            <span className="font-mono text-text">{formatBytes(metrics.cache_storage_bytes)}</span>
          </div>
          <div className={styles.pill} style={{ background: "#080810" }}>
            <span>cache entries</span>
            <span className="font-mono text-text">{metrics.cache_entries ?? 0}</span>
          </div>
          <div className={styles.pill} style={{ background: "#080810" }}>
            <span>output storage</span>
            <span className="font-mono text-text">{formatBytes(metrics.output_storage_bytes)}</span>
          </div>
          <div className={styles.pill} style={{ background: "#080810" }}>
            <span>total storage</span>
            <span className="font-mono text-text">{formatBytes(metrics.total_storage_bytes)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
