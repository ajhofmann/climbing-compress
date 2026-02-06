"use client";

import { useOutputHistory } from "./use-output-history";
import { styles } from "./styles";

function formatAge(timestamp?: number) {
  if (!timestamp) return "";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

function formatDuration(duration?: number | null) {
  if (!duration) return "";
  const seconds = Math.round(duration);
  return `${seconds}s`;
}

function formatOutputType(outputType: string) {
  if (outputType === "main") return "render";
  if (outputType === "comparison") return "compare";
  return outputType;
}

function formatBytes(size?: number | null) {
  if (!size) return "";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)}kb`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)}mb`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)}gb`;
}

export function OutputHistory() {
  const { outputs, error, refresh, loadOutput } = useOutputHistory();

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-magenta)" }}>output history</span>
        <button className={styles.button} onClick={refresh}>Refresh</button>
      </div>

      {error && <span className={styles.empty} style={{ color: "var(--danger)" }}>{error}</span>}

      {outputs.length === 0 ? (
        <span className={styles.empty}>No outputs yet.</span>
      ) : (
        <div className={styles.list}>
          {outputs.slice(0, 5).map((output) => (
            <div key={output.id} className={styles.row}>
              <span className="uppercase text-text-muted">{formatOutputType(output.output_type)}</span>
              <span className={styles.meta}>{formatAge(output.created_at)}</span>
              {output.output_duration && (
                <span className={styles.meta}>{formatDuration(output.output_duration)}</span>
              )}
              {output.size_bytes && (
                <span className={styles.meta}>{formatBytes(output.size_bytes)}</span>
              )}
              <span className={styles.meta}>{output.video_filename ?? output.video_id}</span>
              <span className={styles.meta}>{output.project_name ?? "unassigned"}</span>
              <span className={styles.meta}>{output.id}</span>
              <button className={styles.button} onClick={() => loadOutput(output)}>
                Load
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
