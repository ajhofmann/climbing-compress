"use client";

import { Tooltip } from "@/components/tooltip";

/**
 * Retro hardware toggle switch — chunky, beveled, with LED indicator.
 * Replaces plain checkboxes in the settings panel.
 */
export function Toggle({
  checked,
  onChange,
  label,
  detail,
  color = "cyan",
  title,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  detail?: string;
  color?: "cyan" | "magenta" | "orange" | "lime";
  title?: string;
}) {
  const colors = {
    cyan: { on: "#00e5ff", glow: "rgba(0,229,255,0.5)", bg: "#005f6b" },
    magenta: { on: "#e040fb", glow: "rgba(224,64,251,0.5)", bg: "#5a1a6b" },
    orange: { on: "#ff6e40", glow: "rgba(255,110,64,0.5)", bg: "#6b3520" },
    lime: { on: "#76ff03", glow: "rgba(118,255,3,0.5)", bg: "#2a5f0b" },
  };
  const c = colors[color];

  const content = (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-3 group text-left w-full"
    >
      {/* Switch track */}
      <div
        className="relative shrink-0 w-[44px] h-[22px] rounded-sm transition-all duration-150"
        style={{
          background: checked
            ? `linear-gradient(180deg, ${c.bg} 0%, #12121e 100%)`
            : "linear-gradient(180deg, #1a1a2e 0%, #0a0a14 100%)",
          border: `2px inset ${checked ? c.on : "#333"}`,
          boxShadow: checked
            ? `inset 0 0 8px ${c.glow}, 0 0 6px ${c.glow}`
            : "inset 1px 1px 3px rgba(0,0,0,0.5)",
        }}
      >
        {/* Switch thumb — beveled metal */}
        <div
          className="absolute top-[1px] h-[16px] w-[18px] rounded-sm transition-all duration-150"
          style={{
            left: checked ? "21px" : "1px",
            background: checked
              ? `linear-gradient(180deg, #eee 0%, #999 100%)`
              : "linear-gradient(180deg, #888 0%, #555 100%)",
            border: "1px outset #aaa",
            boxShadow: checked
              ? `0 0 4px ${c.glow}, inset 0 1px 0 rgba(255,255,255,0.4)`
              : "inset 0 1px 0 rgba(255,255,255,0.2), 0 1px 2px rgba(0,0,0,0.4)",
          }}
        >
          {/* Grip lines */}
          <div className="flex flex-col items-center justify-center h-full gap-[2px]">
            <div className="w-[8px] h-[1px] rounded-full" style={{ background: checked ? "rgba(0,0,0,0.3)" : "rgba(0,0,0,0.2)" }} />
            <div className="w-[8px] h-[1px] rounded-full" style={{ background: checked ? "rgba(0,0,0,0.3)" : "rgba(0,0,0,0.2)" }} />
            <div className="w-[8px] h-[1px] rounded-full" style={{ background: checked ? "rgba(0,0,0,0.3)" : "rgba(0,0,0,0.2)" }} />
          </div>
        </div>
      </div>

      {/* LED dot */}
      <div
        className="shrink-0 w-[6px] h-[6px] rounded-full transition-all duration-150"
        style={{
          background: checked ? c.on : "#333",
          boxShadow: checked ? `0 0 4px ${c.on}, 0 0 8px ${c.glow}` : "inset 0 0 1px rgba(0,0,0,0.5)",
        }}
      />

      {/* Label */}
      <div className="flex flex-col">
        <span
          className="text-[10px] font-pixel uppercase tracking-wider transition-colors"
          style={{
            color: checked ? c.on : "var(--text-muted)",
            textShadow: checked ? `0 0 6px ${c.glow}` : "none",
          }}
        >
          {label}
        </span>
        {detail && (
          <span className="text-sm text-text-muted leading-tight">{detail}</span>
        )}
      </div>
    </button>
  );

  return title ? <Tooltip text={title}>{content}</Tooltip> : content;
}
