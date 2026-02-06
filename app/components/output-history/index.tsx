"use client";

import { useOutputHistory } from "./use-output-history";
import { styles } from "./styles";

function formatDate(timestamp?: number) {
  if (!timestamp) return "";
  return new Date(timestamp * 1000).toLocaleTimeString();
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
              <span className="uppercase text-text-muted">{output.output_type}</span>
              <span className={styles.meta}>{formatDate(output.created_at)}</span>
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
