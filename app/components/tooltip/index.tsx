"use client";

import { useState, useRef, useCallback } from "react";

export function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const ref = useRef<HTMLDivElement>(null);
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((e: React.MouseEvent) => {
    if (timeout.current) clearTimeout(timeout.current);
    timeout.current = setTimeout(() => {
      const rect = ref.current?.getBoundingClientRect();
      if (rect) {
        setPos({ x: rect.left + rect.width / 2, y: rect.top });
      }
      setVisible(true);
    }, 400);
  }, []);

  const hide = useCallback(() => {
    if (timeout.current) clearTimeout(timeout.current);
    setVisible(false);
  }, []);

  return (
    <div ref={ref} onMouseEnter={show} onMouseLeave={hide} onMouseDown={hide} className="relative">
      {children}
      {visible && (
        <div
          className="fixed z-50 pointer-events-none"
          style={{
            left: pos.x,
            top: pos.y - 8,
            transform: "translate(-50%, -100%)",
          }}
        >
          <div
            className="px-3 py-2 rounded text-xs font-retro leading-relaxed max-w-[240px] text-center"
            style={{
              background: "#0a0a14",
              border: "1px solid var(--neon-cyan)",
              color: "var(--text)",
              boxShadow: "0 0 12px rgba(0,229,255,0.15), 0 4px 12px rgba(0,0,0,0.6)",
              whiteSpace: "pre-line",
            }}
          >
            {text}
          </div>
          {/* Arrow */}
          <div
            className="mx-auto w-0 h-0"
            style={{
              borderLeft: "5px solid transparent",
              borderRight: "5px solid transparent",
              borderTop: "5px solid var(--neon-cyan)",
            }}
          />
        </div>
      )}
    </div>
  );
}
