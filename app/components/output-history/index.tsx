"use client";

import { useOutputHistory } from "./use-output-history";
import { styles } from "./styles";
import { useStore } from "@/lib/store";
import { formatAge } from "@/lib/format";

function formatDuration(duration?: number | null) {
  if (duration === null || duration === undefined) return "";
  const seconds = Math.round(duration);
  return `${seconds}s`;
}

function formatOutputType(outputType: string) {
  if (outputType === "main") return "render";
  if (outputType === "comparison") return "compare";
  if (outputType === "preview") return "preview";
  return outputType;
}

function formatBytes(size?: number | null) {
  if (size === null || size === undefined) return "";
  if (size === 0) return "0kb";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)}kb`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)}mb`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)}gb`;
}

export function OutputHistory() {
  const { outputs, error, refresh, loadOutput, lastUpdated } = useOutputHistory();
  const { outputId, previewId, comparisonId } = useStore();

  return (
    <div className={styles.panel}>
      <div className="flex items-center justify-between">
        <span className={styles.title} style={{ color: "var(--neon-magenta)" }}>output history</span>
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

      {outputs.length === 0 ? (
        <span className={styles.empty}>No outputs yet.</span>
      ) : (
        <div className={styles.list}>
          {outputs.slice(0, 5).map((output) => (
            <div
              key={output.id}
              className={`${styles.row} ${output.id === outputId || output.id === previewId || output.id === comparisonId ? styles.rowActive : ""}`}
            >
              <span className="uppercase text-text-muted">{formatOutputType(output.output_type)}</span>
              <span className={styles.meta}>{formatAge(output.created_at)}</span>
              {output.output_duration !== null && output.output_duration !== undefined && (
                <span className={styles.meta}>{formatDuration(output.output_duration)}</span>
              )}
              {output.size_bytes !== null && output.size_bytes !== undefined && (
                <span className={styles.meta}>{formatBytes(output.size_bytes)}</span>
              )}
              <span className={styles.meta} title={output.video_filename ?? output.video_id}>
                {output.video_filename ?? output.video_id}
              </span>
              <span className={styles.meta} title={output.project_name ?? "unassigned"}>
                {output.project_name ?? "unassigned"}
              </span>
              <span className={styles.meta} title={output.id}>{output.id.slice(0, 8)}</span>
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
