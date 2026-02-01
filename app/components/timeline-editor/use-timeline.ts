"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Pin } from "@/lib/types";

interface TimelineConfig {
  duration: number;
  maxSpeed: number;
  curve: number[];
  curveTimes: number[];
  pins: Pin[];
  waveformUrl: string;
  onPinsChange: (pins: Pin[]) => void;
}

export function useTimeline(config: TimelineConfig) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const waveImgRef = useRef<HTMLImageElement | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [hoverIdx, setHoverIdx] = useState(-1);

  const { duration, maxSpeed, curve, curveTimes, pins, waveformUrl, onPinsChange } = config;

  // Load waveform image
  useEffect(() => {
    if (!waveformUrl) return;
    const img = new Image();
    img.src = waveformUrl;
    img.onload = () => { waveImgRef.current = img; draw(); };
    waveImgRef.current = img;
  }, [waveformUrl]);

  const timeToX = useCallback((t: number, w: number) => (t / duration) * w, [duration]);
  const xToTime = useCallback((x: number, w: number) => Math.max(0, Math.min(duration, (x / w) * duration)), [duration]);
  const speedToY = useCallback((s: number, h: number) => h - (Math.min(s, maxSpeed) / maxSpeed) * h, [maxSpeed]);
  const yToSpeed = useCallback((y: number, h: number) => Math.max(0.1, Math.min(maxSpeed, (1 - y / h) * maxSpeed)), [maxSpeed]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;

    // Background
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--bg-card").trim() || "#f5f0ea";
    ctx.fillRect(0, 0, w, h);

    // Waveform
    const img = waveImgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      ctx.globalAlpha = 0.4;
      ctx.drawImage(img, 0, 0, w, h);
      ctx.globalAlpha = 1;
    }

    // Grid
    const borderColor = getComputedStyle(document.documentElement).getPropertyValue("--border").trim() || "#d4c9b8";
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 0.5;
    for (let t = 5; t < duration; t += 5) {
      const x = timeToX(t, w);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text-muted").trim() || "#8a7d6e";
      ctx.font = "9px system-ui";
      ctx.fillText(`${t}s`, x + 2, h - 3);
    }
    for (let s = 2; s <= maxSpeed; s += 2) {
      const y = speedToY(s, h);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      ctx.fillText(`${s}x`, 3, y - 2);
    }

    // 1x reference
    const refY = speedToY(1, h);
    ctx.strokeStyle = borderColor;
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, refY); ctx.lineTo(w, refY); ctx.stroke();
    ctx.setLineDash([]);

    // Auto curve
    if (curveTimes.length > 0 && curve.length > 0) {
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#3d5a3e";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < curveTimes.length; i++) {
        const x = timeToX(curveTimes[i], w);
        const y = speedToY(curve[i], h);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Pin points
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#3d5a3e";
    const warmColor = getComputedStyle(document.documentElement).getPropertyValue("--warm").trim() || "#c97b2a";

    for (let i = 0; i < pins.length; i++) {
      const x = timeToX(pins[i].time, w);
      const y = speedToY(pins[i].speed, h);
      const isHover = i === hoverIdx;
      const isDrag = dragging === i;

      // Glow
      ctx.beginPath();
      ctx.arc(x, y, isDrag ? 12 : 9, 0, Math.PI * 2);
      ctx.fillStyle = isDrag ? `${warmColor}40` : `${accentColor}20`;
      ctx.fill();

      // Circle
      ctx.beginPath();
      ctx.arc(x, y, isDrag ? 8 : 6, 0, Math.PI * 2);
      ctx.fillStyle = isDrag ? warmColor : (isHover ? accentColor : accentColor);
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Tooltip
      if (isHover || isDrag) {
        const label = `${pins[i].speed.toFixed(1)}x @ ${pins[i].time.toFixed(1)}s`;
        ctx.font = "bold 11px system-ui";
        const tw = ctx.measureText(label).width;
        const lx = Math.min(x - tw / 2, w - tw - 8);
        const ly = y - 18;

        ctx.fillStyle = "rgba(0,0,0,0.75)";
        ctx.beginPath();
        const rx = Math.max(4, lx - 4);
        ctx.roundRect(rx, ly - 12, tw + 8, 16, 4);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.fillText(label, Math.max(8, lx), ly);
      }
    }
  }, [curve, curveTimes, pins, duration, maxSpeed, hoverIdx, dragging, timeToX, speedToY]);

  // Redraw on changes
  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [draw]);

  const getPos = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const findNear = useCallback((pos: { x: number; y: number }, threshold = 15) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    for (let i = 0; i < pins.length; i++) {
      const px = timeToX(pins[i].time, rect.width);
      const py = speedToY(pins[i].speed, rect.height);
      const d = Math.sqrt((pos.x - px) ** 2 + (pos.y - py) ** 2);
      if (d < threshold) return i;
    }
    return -1;
  }, [pins, timeToX, speedToY]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const pos = getPos(e);
    const rect = canvasRef.current!.getBoundingClientRect();

    if (e.button === 2) {
      const idx = findNear(pos);
      if (idx >= 0) {
        const next = pins.filter((_, j) => j !== idx);
        onPinsChange(next);
      }
      return;
    }

    const idx = findNear(pos);
    if (idx >= 0) {
      setDragging(idx);
    } else {
      const t = xToTime(pos.x, rect.width);
      const s = yToSpeed(pos.y, rect.height);
      const next = [...pins, { time: t, speed: s }];
      onPinsChange(next);
      setDragging(next.length - 1);
    }
  }, [pins, findNear, getPos, onPinsChange, xToTime, yToSpeed]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const pos = getPos(e);
    const rect = canvasRef.current!.getBoundingClientRect();

    if (dragging !== null) {
      const t = xToTime(pos.x, rect.width);
      const s = yToSpeed(pos.y, rect.height);
      const next = pins.map((p, i) => i === dragging ? { time: t, speed: s } : p);
      onPinsChange(next);
    } else {
      const idx = findNear(pos);
      setHoverIdx(idx);
      if (canvasRef.current) {
        canvasRef.current.style.cursor = idx >= 0 ? "grab" : "crosshair";
      }
    }
  }, [dragging, pins, findNear, getPos, onPinsChange, xToTime, yToSpeed]);

  const onMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  const onMouseLeave = useCallback(() => {
    setDragging(null);
    setHoverIdx(-1);
  }, []);

  const onContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
  }, []);

  return {
    canvasRef,
    handlers: { onMouseDown, onMouseMove, onMouseUp, onMouseLeave, onContextMenu },
  };
}
