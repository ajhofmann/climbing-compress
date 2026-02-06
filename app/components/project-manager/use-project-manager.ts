"use client";

import { useCallback, useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { assignVideoProject, createProject, listProjects, updateProject, getProjectSummary, deleteProject } from "@/lib/api";
import { ProjectSummary } from "@/lib/types";

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
  const [summary, setSummary] = useState<ProjectSummary | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjects();
      setProjects(data);
      const stored = typeof window !== "undefined" ? window.localStorage.getItem("projectId") : null;
      if (stored === "unassigned") {
        setSelectedProjectId(null);
        return;
      }
      if (!selectedProjectId && data.length > 0) {
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

  const refreshSummary = useCallback(async (projectId: string | null) => {
    const targetId = projectId ?? "unassigned";
    try {
      const data = await getProjectSummary(targetId);
      setSummary(data);
    } catch {
      setSummary(null);
    }
  }, []);

  useEffect(() => {
    refreshSummary(selectedProjectId);
    const id = window.setInterval(() => refreshSummary(selectedProjectId), 6000);
    return () => window.clearInterval(id);
  }, [refreshSummary, selectedProjectId]);

  const selectProject = useCallback(async (projectId: string | null) => {
    setSelectedProjectId(projectId);
    if (typeof window !== "undefined") {
      if (projectId) {
        window.localStorage.setItem("projectId", projectId);
      } else {
        window.localStorage.setItem("projectId", "unassigned");
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

  const remove = useCallback(async (projectId: string) => {
    setLoading(true);
    setError(null);
    try {
      await deleteProject(projectId);
      const updated = projects.filter((p) => p.id !== projectId);
      setProjects(updated);
      setSelectedProjectId(null);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("projectId", "unassigned");
      }
      setSummary(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete project";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projects, setProjects, setSelectedProjectId]);

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
    summary,
    remove,
  };
}
