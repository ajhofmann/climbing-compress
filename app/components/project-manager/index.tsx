"use client";

import { useState } from "react";
import { useProjectManager } from "./use-project-manager";
import { styles } from "./styles";

export function ProjectManager() {
  const { projects, selectedProjectId, loading, error, refresh, selectProject, create, update, summary } = useProjectManager();
  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const selected = projects.find((project) => project.id === selectedProjectId) ?? null;

  const onCreate = async () => {
    const created = await create(name, description);
    if (created) {
      setName("");
      setDescription("");
      setIsCreating(false);
    }
  };

  const onEdit = async () => {
    if (!selected) return;
    const updated = await update(selected.id, name, description);
    if (updated) {
      setIsEditing(false);
    }
  };

  const startEdit = () => {
    if (!selected) return;
    setName(selected.name);
    setDescription(selected.description ?? "");
    setIsEditing(true);
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label} style={{ color: "var(--neon-cyan)" }}>Project</span>
        <div className={styles.row}>
          <button className={styles.button} onClick={() => setIsCreating((v) => !v)}>
            {isCreating ? "Cancel" : "New"}
          </button>
          {selected && !isEditing && (
            <button className={styles.button} onClick={startEdit}>
              Edit
            </button>
          )}
          <button className={styles.button} onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      <div className={styles.row}>
        <select
          className={styles.select}
          value={selectedProjectId ?? ""}
          onChange={(e) => selectProject(e.target.value || null)}
          disabled={loading}
        >
          <option value="">Unassigned</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        {loading && <span className={styles.helper}>Loading...</span>}
        {error && <span className={styles.helper} style={{ color: "var(--danger)" }}>{error}</span>}
      </div>

      {selected?.description && (
        <p className={styles.helper}>{selected.description}</p>
      )}

      {summary && (
        <div className="flex gap-3 text-[10px] text-text-muted flex-wrap">
          <span>videos: <span className="font-mono text-text">{summary.videos}</span></span>
          <span>outputs: <span className="font-mono text-text">{summary.outputs}</span></span>
          <span>jobs: <span className="font-mono text-text">{summary.jobs}</span></span>
          {summary.latest_output && (
            <span>latest: <span className="font-mono text-text">{summary.latest_output.output_type}</span></span>
          )}
        </div>
      )}

      {isCreating && (
        <div className="flex flex-col gap-2">
          <input
            className={styles.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
          />
          <textarea
            className={styles.textarea}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            rows={2}
          />
          <div className={styles.row}>
            <button
              className={styles.button}
              onClick={onCreate}
              disabled={!name.trim() || loading}
            >
              Create
            </button>
          </div>
        </div>
      )}

      {isEditing && (
        <div className="flex flex-col gap-2">
          <input
            className={styles.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
          />
          <textarea
            className={styles.textarea}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            rows={2}
          />
          <div className={styles.row}>
            <button
              className={styles.button}
              onClick={onEdit}
              disabled={!name.trim() || loading}
            >
              Save
            </button>
            <button className={styles.button} onClick={() => setIsEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
