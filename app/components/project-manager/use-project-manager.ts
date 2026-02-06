"use client";

import { useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { assignVideoProject, createProject, listProjects, updateProject } from "@/lib/api";

export function useProjectManager() {
  const {
    projects,
    setProjects,
    addProject,
    selectedProjectId,
    setSelectedProjectId,
    videoId,
    setProgress,
  } = useStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjects();
      setProjects(data);
      if (!selectedProjectId && data.length > 0) {
        const stored = typeof window !== "undefined" ? window.localStorage.getItem("projectId") : null;
        const match = stored ? data.find((p) => p.id === stored) : null;
        setSelectedProjectId(match?.id ?? data[0].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load projects";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId, setProjects, setSelectedProjectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectProject = useCallback(async (projectId: string | null) => {
    setSelectedProjectId(projectId);
    if (typeof window !== "undefined") {
      if (projectId) {
        window.localStorage.setItem("projectId", projectId);
      } else {
        window.localStorage.removeItem("projectId");
      }
    }
    if (videoId) {
      try {
        await assignVideoProject(videoId, projectId);
        if (projectId) {
          setProgress(0, "Video assigned to project");
        } else {
          setProgress(0, "Video removed from project");
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to assign project";
        setProgress(0, msg);
      }
    }
  }, [setSelectedProjectId, videoId, setProgress]);

  const create = useCallback(async (name: string, description?: string) => {
    if (!name.trim()) return null;
    setLoading(true);
    setError(null);
    try {
      const project = await createProject(name.trim(), description?.trim() || undefined);
      addProject(project);
      await selectProject(project.id);
      return project;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create project";
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [addProject, selectProject]);

  const update = useCallback(async (projectId: string, name: string, description?: string) => {
    if (!name.trim()) return null;
    setLoading(true);
    setError(null);
    try {
      const project = await updateProject(projectId, name.trim(), description?.trim() || undefined);
      const updated = projects.map((p) => (p.id === project.id ? project : p));
      setProjects(updated);
      return project;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update project";
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, [projects, setProjects]);

  useEffect(() => {
    if (!videoId || !selectedProjectId) return;
    assignVideoProject(videoId, selectedProjectId).catch(() => undefined);
  }, [videoId, selectedProjectId]);

  return {
    projects,
    selectedProjectId,
    loading,
    error,
    refresh,
    selectProject,
    create,
    update,
  };
}
