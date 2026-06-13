"use client";

import { useEffect, useMemo, useState } from "react";
import { RenderHistoryItem } from "@/lib/api";
import { useStore } from "@/lib/store";
import { useRenderHistory } from "./use-render-history";
import { renderHistoryStyles } from "./styles";
import { Tooltip } from "@/components/tooltip";
import { sound } from "@/lib/sound";

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

function formatShortDate(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "??/??";
  const d = new Date(ms);
  return `${d.getMonth() + 1}/${d.getDate()}`;
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

const MODE_STRIPES: Record<string, string> = {
  progress: "var(--neon-cyan)",
  action: "var(--neon-magenta)",
  hybrid: "var(--neon-orange)",
  dynamic: "var(--neon-lime)",
};

function buildSpineTooltip(entry: RenderHistoryItem) {
  const lines = [
    `${formatTimestamp(entry.created_at)}`,
    `out ${entry.stats.output_duration.toFixed(1)}s · spd ${entry.stats.speed_min.toFixed(1)}x-${entry.stats.speed_max.toFixed(1)}x`,
    `mode ${entry.settings.mode}/${entry.settings.edit_mode} · target ${entry.settings.target_duration.toFixed(1)}s`,
    `trim ${formatTrim(entry)} · fps ${entry.settings.output_fps.toFixed(0)} · scale ${entry.settings.scale.toFixed(2)} · crf ${entry.settings.crf}`,
    `${formatBytes(entry.output_bytes)}${entry.comparison_id ? ` · A/B ${formatBytes(entry.comparison_bytes)}` : ""}`,
    "",
    "click to load this tape into the deck",
  ];
  return lines.join("\n");
}

interface RenderHistoryTimelineProps {
  videoId: string | null;
  refreshToken?: number;
}

export function RenderHistoryTimeline({ videoId, refreshToken = 0 }: RenderHistoryTimelineProps) {
  const outputId = useStore((s) => s.outputId);
  const setOutputId = useStore((s) => s.setOutputId);
  const setComparisonId = useStore((s) => s.setComparisonId);
  const { entries, isLoading, error, refresh } = useRenderHistory(videoId);
  const [copiedOutputId, setCopiedOutputId] = useState<string | null>(null);
  const canCopy = typeof window !== "undefined" && !!window.navigator?.clipboard?.writeText;

  const title = useMemo(
    () => `tape shelf · past renders (${entries.length})`,
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
    <section className={renderHistoryStyles.wrap} aria-label="Past render history tape shelf">
      <div className={renderHistoryStyles.header}>
        <span className={renderHistoryStyles.title}>{title}</span>
        <div className={renderHistoryStyles.actions}>
          <button
            onClick={() => void refresh()}
            disabled={isLoading}
            className={renderHistoryStyles.button}
            aria-label="Refresh render history"
          >
            {isLoading ? "[refreshing...]" : "[refresh shelf]"}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm font-pixel text-rose-300/85 mb-2">
          failed to load render history: {error}
        </div>
      )}

      {entries.length <= 0 ? (
        <div className="text-sm font-pixel text-text-muted/70 py-2">
          no tapes on the shelf yet — hit ● RENDER to dub one
        </div>
      ) : (
        <div>
          <div className="vhs-shelf" role="list">
            {entries.map((entry, idx) => {
              const isActive = entry.output_id === outputId;
              const copied = copiedOutputId === entry.output_id;
              const renderNo = entries.length - idx;
              const mode = entry.settings?.mode ?? "progress";
              const stripe = MODE_STRIPES[mode] ?? "var(--neon-cyan)";
              return (
                <Tooltip key={entry.output_id} text={buildSpineTooltip(entry)}>
                  <div
                    role="listitem"
                    tabIndex={0}
                    aria-current={isActive ? "true" : undefined}
                    aria-label={`Load past render ${renderNo}: ${buildRenderLabel(entry)}`}
                    className={`vhs-spine ${isActive ? "vhs-spine--active" : ""}`}
                    onClick={() => {
                      sound.tapeInsert();
                      setOutputId(entry.output_id);
                      setComparisonId(entry.comparison_id ?? null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        sound.tapeInsert();
                        setOutputId(entry.output_id);
                        setComparisonId(entry.comparison_id ?? null);
                      }
                    }}
                  >
                    <span className="vhs-spine-corner">{entry.comparison_id ? "A/B" : "SP"}</span>
                    <div className="vhs-spine-label">
                      <div className="vhs-spine-stripe" style={{ background: stripe }} />
                      <span className="vhs-spine-title">
                        #{renderNo} · {mode} · {entry.stats.output_duration.toFixed(0)}s
                      </span>
                      <span className="vhs-spine-meta">{formatShortDate(entry.created_at)}</span>
                    </div>
                    {isActive && (
                      <span
                        className="absolute -top-5 left-1/2 -translate-x-1/2 font-pixel text-[7px] tracking-[0.15em] whitespace-nowrap"
                        style={{ color: "var(--neon-cyan)", textShadow: "0 0 6px rgba(0,229,255,0.5)" }}
                      >
                        IN DECK
                      </span>
                    )}
                    <span className="vhs-spine-action">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!canCopy) return;
                          void window.navigator.clipboard.writeText(buildRenderLabel(entry));
                          setCopiedOutputId(entry.output_id);
                          window.setTimeout(() => {
                            setCopiedOutputId((prevId) => (prevId === entry.output_id ? null : prevId));
                          }, 1000);
                        }}
                        disabled={!canCopy}
                        className="font-pixel text-[7px] tracking-wider px-1 py-0.5 rounded border border-cyan-500/30 text-cyan-300 hover:text-white hover:border-cyan-300 bg-black/70 disabled:opacity-45 disabled:cursor-not-allowed"
                        aria-label={`Copy summary for render ${entry.output_id}`}
                      >
                        {copied ? "COPIED" : "COPY"}
                      </button>
                    </span>
                  </div>
                </Tooltip>
              );
            })}
          </div>
          <div className="vhs-shelf-rail" />
        </div>
      )}
    </section>
  );
}
