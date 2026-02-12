"use client";

import { Tooltip } from "@/components/tooltip";

export function ToggleSwitch({ label, checked, onChange, color = "#00e5ff", title, disabled = false }: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  color?: string;
  title?: string;
  disabled?: boolean;
}) {
  const content = (
    <button
      onClick={() => { if (!disabled) onChange(!checked); }}
      className={`flex flex-col items-center gap-1 select-none group ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
      style={{ minWidth: 64 }}
    >
      <span className="rack-section-label text-center">{label}</span>

      <div className="relative flex flex-col items-center">
        {/* Toggle switch image */}
        <div
          className="w-[44px] h-[56px] bg-contain bg-center bg-no-repeat transition-transform duration-100"
          style={{
            backgroundImage: "url('/retro/toggle-switch.png')",
            transform: checked ? "scaleY(1)" : "scaleY(-1)",
            filter: checked
              ? `drop-shadow(0 0 4px ${color}40)`
              : disabled ? "brightness(0.4)" : "brightness(0.7)",
          }}
        />

        {/* Pilot light */}
        <div
          className="w-[10px] h-[10px] rounded-full mt-1 transition-all duration-150"
          style={{
            background: checked ? color : "#1a1a2e",
            boxShadow: checked
              ? `0 0 4px ${color}, 0 0 8px ${color}60`
              : "inset 0 1px 2px rgba(0,0,0,0.5)",
            border: checked ? "none" : "1px solid #333",
          }}
        />
      </div>

      {/* State label */}
      <span
        className="text-sm font-pixel uppercase tracking-wide transition-colors"
        style={{
          color: checked ? color : "var(--text-muted)",
          textShadow: checked ? `0 0 4px ${color}60` : "none",
        }}
      >
        {checked ? "ON" : "OFF"}
      </span>
    </button>
  );

  return title ? <Tooltip text={title}>{content}</Tooltip> : content;
}
