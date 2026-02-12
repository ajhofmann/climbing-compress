"use client";

import { useEffect, useMemo, useState } from "react";
import { RenderHistoryItem } from "@/lib/api";
import { useStore } from "@/lib/store";
import { useRenderHistory } from "./use-render-history";
import { renderHistoryStyles } from "./styles";

function formatBytes(bytes: number | null | undefined) {
  if (bytes == null || !Number.isFinite(bytes)) return "?";
  const value = Math.max(0, bytes);
  if (value < 1024) return `${value.toFixed(0)} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatTimestamp(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "unknown";
  return new Date(ms).toLocaleString();
}

function formatTrim(entry: RenderHistoryItem) {
  const start = entry.settings?.trim_start ?? 0;
  const end = entry.settings?.trim_end ?? 0;
  return `${start.toFixed(1)}s-${end.toFixed(1)}s`;
}

function buildRenderLabel(entry: RenderHistoryItem) {
  const duration = entry.stats?.output_duration ?? 0;
  const mode = entry.settings?.mode ?? "unknown";
  const target = entry.settings?.target_duration ?? 0;
  return `${entry.video_filename ?? entry.video_id} · ${mode} · out ${duration.toFixed(1)}s · target ${target.toFixed(1)}s · id ${entry.output_id}`;
}

interface RenderHistoryTimelineProps {
  videoId: string | null;
  refreshToken?: number;
}

export function RenderHistoryTimeline({ videoId, refreshToken = 0 }: RenderHistoryTimelineProps) {
  const outputId = useStore((s) => s.outputId);
  const comparisonId = useStore((s) => s.comparisonId);
  const setOutputId = useStore((s) => s.setOutputId);
  const setComparisonId = useStore((s) => s.setComparisonId);
  const { entries, isLoading, error, refresh } = useRenderHistory(videoId);
  const [copiedOutputId, setCopiedOutputId] = useState<string | null>(null);
  const canCopy = typeof window !== "undefined" && !!window.navigator?.clipboard?.writeText;

  const title = useMemo(
    () => `Past renders (${entries.length})`,
    [entries.length],
  );

  useEffect(() => {
    if (!videoId || refreshToken <= 0) return;
    let cancelled = false;
    const refreshSoon = window.setTimeout(() => {
      if (cancelled) return;
      void refresh();
    }, 180);
    const refreshRetry = window.setTimeout(() => {
      if (cancelled) return;
      void refresh();
    }, 800);
    return () => {
      cancelled = true;
      window.clearTimeout(refreshSoon);
      window.clearTimeout(refreshRetry);
    };
  }, [videoId, refreshToken, refresh]);

  if (!videoId) return null;

  return (
    <section className={renderHistoryStyles.wrap} aria-label="Past render history timeline">
      <div className={renderHistoryStyles.header}>
        <span className={renderHistoryStyles.title}>{title}</span>
        <div className={renderHistoryStyles.actions}>
          <button
            onClick={() => void refresh()}
            disabled={isLoading}
            className={renderHistoryStyles.button}
            aria-label="Refresh render history"
          >
            {isLoading ? "[refreshing...]" : "[refresh history]"}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-[9px] font-pixel text-rose-300/85 mb-2">
          failed to load render history: {error}
        </div>
      )}

      {entries.length <= 0 ? (
        <div className="text-[9px] font-pixel text-text-muted/70">no past renders for this clip yet</div>
      ) : (
        <div className={renderHistoryStyles.timelineRail}>
          <div className={renderHistoryStyles.timelineTrack}>
            {entries.map((entry, idx) => {
              const isActive = entry.output_id === outputId;
              const copied = copiedOutputId === entry.output_id;
              return (
                <article
                  key={entry.output_id}
                  className={`${renderHistoryStyles.card} ${isActive ? renderHistoryStyles.cardActive : ""}`}
                  aria-current={isActive ? "true" : undefined}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[8px] font-pixel text-cyan-300/85">render #{entries.length - idx}</span>
                    <span className="text-[8px] font-pixel text-text-muted/75">
                      {formatTimestamp(entry.created_at)}
                    </span>
                  </div>

                  <div className="text-[9px] font-pixel text-cyan-100 break-all">
                    {entry.output_id}
                  </div>

                  <div className="text-[8px] font-pixel text-text-muted/80 leading-tight">
                    out {entry.stats.output_duration.toFixed(1)}s · spd {entry.stats.speed_min.toFixed(1)}x-{entry.stats.speed_max.toFixed(1)}x
                  </div>
                  <div className="text-[8px] font-pixel text-text-muted/75 leading-tight">
                    mode {entry.settings.mode}/{entry.settings.edit_mode} · target {entry.settings.target_duration.toFixed(1)}s · trim {formatTrim(entry)}
                  </div>
                  <div className="text-[8px] font-pixel text-text-muted/75 leading-tight">
                    fps {entry.settings.output_fps.toFixed(0)} · scale {entry.settings.scale.toFixed(2)} · crf {entry.settings.crf}
                  </div>
                  <div className="text-[8px] font-pixel text-text-muted/75 leading-tight">
                    bytes {formatBytes(entry.output_bytes)}
                    {entry.comparison_id ? ` · compare ${formatBytes(entry.comparison_bytes)}` : ""}
                  </div>

                  <div className="pt-0.5 flex items-center gap-1">
                    <button
                      onClick={() => {
                        setOutputId(entry.output_id);
                        setComparisonId(entry.comparison_id ?? null);
                      }}
                      className="px-1.5 py-0.5 border rounded border-cyan-400/45 text-cyan-200 hover:text-white hover:border-cyan-300 text-[9px] font-pixel uppercase"
                      aria-label={`Load past render ${entry.output_id}`}
                    >
                      {isActive && entry.comparison_id === comparisonId ? "loaded" : "load"}
                    </button>
                    <button
                      onClick={() => {
                        if (!canCopy) return;
                        void window.navigator.clipboard.writeText(buildRenderLabel(entry));
                        setCopiedOutputId(entry.output_id);
                        window.setTimeout(() => {
                          setCopiedOutputId((prev) => (prev === entry.output_id ? null : prev));
                        }, 1000);
                      }}
                      disabled={!canCopy}
                      className="px-1.5 py-0.5 border rounded border-cyan-500/30 text-cyan-300 hover:text-white hover:border-cyan-300 text-[9px] font-pixel uppercase disabled:opacity-45 disabled:cursor-not-allowed"
                      aria-label={`Copy summary for render ${entry.output_id}`}
                    >
                      {copied ? "copied" : "copy"}
                    </button>
                    {entry.comparison_id && (
                      <span className="text-[8px] font-pixel text-amber-200/90">A/B</span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

