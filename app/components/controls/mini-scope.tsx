"use client";

import { useEffect, useRef } from "react";
import { useStore } from "@/lib/store";

export function MiniScope() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const curve = useStore((s) => s.curve);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = "#060a08";
    ctx.fillRect(0, 0, w, h);

    // Grid lines (phosphor green, very faint)
    ctx.strokeStyle = "rgba(0,200,100,0.08)";
    ctx.lineWidth = 0.5;
    for (let x = 0; x <= w; x += w / 8) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y <= h; y += h / 4) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Center line (brighter)
    ctx.strokeStyle = "rgba(0,200,100,0.15)";
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    if (!curve || curve.length < 2) {
      // No signal
      ctx.strokeStyle = "rgba(0,229,255,0.3)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();

      ctx.fillStyle = "rgba(0,229,255,0.4)";
      const pixelFont = getComputedStyle(document.documentElement)
        .getPropertyValue("--font-pixel")
        .trim();
      ctx.font = `11px ${pixelFont || "monospace"}`;
      ctx.textAlign = "center";
      ctx.fillText("NO SIGNAL", w / 2, h / 2 + 3);
      return;
    }

    // Find curve range for normalization
    let cMin = Infinity, cMax = -Infinity;
    for (const v of curve) {
      if (v < cMin) cMin = v;
      if (v > cMax) cMax = v;
    }
    const range = cMax - cMin || 1;

    // Draw glow pass (thicker, semi-transparent)
    ctx.strokeStyle = "rgba(0,229,255,0.2)";
    ctx.lineWidth = 4;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = 0; i < curve.length; i++) {
      const x = (i / (curve.length - 1)) * w;
      const y = h - ((curve[i] - cMin) / range) * (h - 8) - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw main trace
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < curve.length; i++) {
      const x = (i / (curve.length - 1)) * w;
      const y = h - ((curve[i] - cMin) / range) * (h - 8) - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw bright core trace
    ctx.strokeStyle = "rgba(150,240,255,0.6)";
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    for (let i = 0; i < curve.length; i++) {
      const x = (i / (curve.length - 1)) * w;
      const y = h - ((curve[i] - cMin) / range) * (h - 8) - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [curve]);

  return (
    <div className="crt-scope">
      <canvas
        ref={canvasRef}
        width={200}
        height={60}
        className="w-full h-auto rounded-sm"
      />
    </div>
  );
}
