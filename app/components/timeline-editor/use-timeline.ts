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
  trimStart: number;
  trimEnd: number;
  onTrimChange: (start: number, end: number) => void;
}

const DEFAULT_PIN_RADIUS = 2.0;

type DragTarget =
  | { type: "pin"; index: number }
  | { type: "trim-start" }
  | { type: "trim-end" }
  | null;

export function useTimeline(config: TimelineConfig) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const waveImgRef = useRef<HTMLImageElement | null>(null);
  const [dragging, setDragging] = useState<DragTarget>(null);
  const [hoverIdx, setHoverIdx] = useState(-1);
  const [hoverTrim, setHoverTrim] = useState<"start" | "end" | null>(null);

  const { duration, maxSpeed, curve, curveTimes, pins, waveformUrl, onPinsChange, trimStart, trimEnd, onTrimChange } = config;

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
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
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

    // Trim dimmed regions
    const trimX0 = timeToX(trimStart, w);
    const trimX1 = timeToX(trimEnd > 0 ? trimEnd : duration, w);

    if (trimX0 > 0) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      ctx.fillRect(0, 0, trimX0, h);
    }
    if (trimX1 < w) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      ctx.fillRect(trimX1, 0, w - trimX1, h);
    }

    // Trim handles
    const handleW = 6;
    const trimHandleColor = "#e8863a";
    const trimHoverStart = hoverTrim === "start" || (dragging?.type === "trim-start");
    const trimHoverEnd = hoverTrim === "end" || (dragging?.type === "trim-end");

    // Start handle
    ctx.fillStyle = trimHoverStart ? "#ff9f55" : trimHandleColor;
    ctx.beginPath();
    ctx.roundRect(trimX0 - handleW / 2, 0, handleW, h, 3);
    ctx.fill();
    // Grip lines
    ctx.strokeStyle = "rgba(255,255,255,0.7)";
    ctx.lineWidth = 1;
    for (let gy = h * 0.35; gy < h * 0.65; gy += 5) {
      ctx.beginPath();
      ctx.moveTo(trimX0 - 1.5, gy);
      ctx.lineTo(trimX0 + 1.5, gy);
      ctx.stroke();
    }

    // End handle
    ctx.fillStyle = trimHoverEnd ? "#ff9f55" : trimHandleColor;
    ctx.beginPath();
    ctx.roundRect(trimX1 - handleW / 2, 0, handleW, h, 3);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.7)";
    ctx.lineWidth = 1;
    for (let gy = h * 0.35; gy < h * 0.65; gy += 5) {
      ctx.beginPath();
      ctx.moveTo(trimX1 - 1.5, gy);
      ctx.lineTo(trimX1 + 1.5, gy);
      ctx.stroke();
    }

    // Trim time labels
    ctx.font = "bold 10px system-ui";
    ctx.fillStyle = trimHandleColor;
    if (trimStart > 0) {
      const label = `${trimStart.toFixed(1)}s`;
      ctx.fillText(label, trimX0 + 4, 12);
    }
    if (trimEnd > 0 && trimEnd < duration) {
      const label = `${trimEnd.toFixed(1)}s`;
      const tw2 = ctx.measureText(label).width;
      ctx.fillText(label, trimX1 - tw2 - 4, 12);
    }

    // Pin points
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#3d5a3e";
    const warmColor = getComputedStyle(document.documentElement).getPropertyValue("--warm").trim() || "#c97b2a";

    for (let i = 0; i < pins.length; i++) {
      const pin = pins[i];
      const x = timeToX(pin.time, w);
      const y = speedToY(pin.speed, h);
      const isHover = i === hoverIdx;
      const isDrag = dragging?.type === "pin" && dragging.index === i;
      const radiusS = pin.radius ?? DEFAULT_PIN_RADIUS;

      // Radius influence zone — translucent bell shape
      const radiusPx = timeToX(radiusS, w);
      if (radiusPx > 2 && (isHover || isDrag)) {
        const grad = ctx.createRadialGradient(x, y, 0, x, y, radiusPx);
        grad.addColorStop(0, isDrag ? `${warmColor}30` : `${accentColor}20`);
        grad.addColorStop(1, "transparent");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.ellipse(x, y, radiusPx, h * 0.6, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // Radius bracket lines (subtle, always visible)
      const rLeftX = timeToX(pin.time - radiusS, w);
      const rRightX = timeToX(pin.time + radiusS, w);
      ctx.strokeStyle = isDrag ? `${warmColor}50` : `${accentColor}25`;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(rLeftX, 0); ctx.lineTo(rLeftX, h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(rRightX, 0); ctx.lineTo(rRightX, h); ctx.stroke();
      ctx.setLineDash([]);

      // Glow
      ctx.beginPath();
      ctx.arc(x, y, isDrag ? 12 : 9, 0, Math.PI * 2);
      ctx.fillStyle = isDrag ? `${warmColor}40` : `${accentColor}20`;
      ctx.fill();

      // Circle
      ctx.beginPath();
      ctx.arc(x, y, isDrag ? 8 : 6, 0, Math.PI * 2);
      ctx.fillStyle = isDrag ? warmColor : accentColor;
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Tooltip
      if (isHover || isDrag) {
        const label = `${pin.speed.toFixed(1)}x @ ${pin.time.toFixed(1)}s  r=${radiusS.toFixed(1)}s`;
        ctx.font = "bold 11px system-ui";
        const tw2 = ctx.measureText(label).width;
        const lx = Math.min(x - tw2 / 2, w - tw2 - 8);
        const ly = y - 18;

        ctx.fillStyle = "rgba(0,0,0,0.75)";
        ctx.beginPath();
        const rx2 = Math.max(4, lx - 4);
        ctx.roundRect(rx2, ly - 12, tw2 + 8, 16, 4);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.fillText(label, Math.max(8, lx), ly);
      }
    }
  }, [curve, curveTimes, pins, duration, maxSpeed, hoverIdx, dragging, trimStart, trimEnd, hoverTrim, timeToX, speedToY]);

  // Redraw on changes
  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [draw]);

  const getPos = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const findNear = useCallback((pos: { x: number; y: number }, threshold = 15) => {
    const canvas = canvasRef.current;
    if (!canvas) return -1;
    const rect = canvas.getBoundingClientRect();
    for (let i = 0; i < pins.length; i++) {
      const px = timeToX(pins[i].time, rect.width);
      const py = speedToY(pins[i].speed, rect.height);
      const d = Math.sqrt((pos.x - px) ** 2 + (pos.y - py) ** 2);
      if (d < threshold) return i;
    }
    return -1;
  }, [pins, timeToX, speedToY]);

  const findNearTrim = useCallback((pos: { x: number; y: number }, threshold = 10): "start" | "end" | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const startX = timeToX(trimStart, rect.width);
    const endX = timeToX(trimEnd > 0 ? trimEnd : duration, rect.width);
    if (Math.abs(pos.x - startX) < threshold) return "start";
    if (Math.abs(pos.x - endX) < threshold) return "end";
    return null;
  }, [trimStart, trimEnd, duration, timeToX]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const pos = getPos(e);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    if (e.button === 2) {
      const idx = findNear(pos);
      if (idx >= 0) {
        const next = pins.filter((_, j) => j !== idx);
        onPinsChange(next);
      }
      return;
    }

    // Check trim handles first (they take priority at edges)
    const trimHit = findNearTrim(pos);
    if (trimHit === "start") {
      setDragging({ type: "trim-start" });
      return;
    }
    if (trimHit === "end") {
      setDragging({ type: "trim-end" });
      return;
    }

    // Then check pins
    const idx = findNear(pos);
    if (idx >= 0) {
      setDragging({ type: "pin", index: idx });
    } else {
      const t = xToTime(pos.x, rect.width);
      const s = yToSpeed(pos.y, rect.height);
      const next = [...pins, { time: t, speed: s, radius: DEFAULT_PIN_RADIUS }];
      onPinsChange(next);
      setDragging({ type: "pin", index: next.length - 1 });
    }
  }, [pins, findNear, findNearTrim, getPos, onPinsChange, xToTime, yToSpeed]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const pos = getPos(e);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    if (dragging !== null) {
      if (dragging.type === "trim-start") {
        const t = xToTime(pos.x, rect.width);
        const effectiveEnd = trimEnd > 0 ? trimEnd : duration;
        const clamped = Math.max(0, Math.min(t, effectiveEnd - 1));
        onTrimChange(clamped, trimEnd);
      } else if (dragging.type === "trim-end") {
        const t = xToTime(pos.x, rect.width);
        const clamped = Math.max(trimStart + 1, Math.min(t, duration));
        onTrimChange(trimStart, clamped);
      } else if (dragging.type === "pin") {
        const t = xToTime(pos.x, rect.width);
        const s = yToSpeed(pos.y, rect.height);
        const next = pins.map((p, i) => i === dragging.index ? { time: t, speed: s } : p);
        onPinsChange(next);
      }
    } else {
      // Check trim hover first
      const trimHit = findNearTrim(pos);
      setHoverTrim(trimHit);

      const idx = findNear(pos);
      setHoverIdx(idx);
      if (canvasRef.current) {
        if (trimHit) {
          canvasRef.current.style.cursor = "col-resize";
        } else if (idx >= 0) {
          canvasRef.current.style.cursor = "grab";
        } else {
          canvasRef.current.style.cursor = "crosshair";
        }
      }
    }
  }, [dragging, pins, trimStart, trimEnd, duration, findNear, findNearTrim, getPos, onPinsChange, onTrimChange, xToTime, yToSpeed]);

  const onMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  const onMouseLeave = useCallback(() => {
    setDragging(null);
    setHoverIdx(-1);
    setHoverTrim(null);
  }, []);

  const onWheel = useCallback((e: React.WheelEvent) => {
    // Scroll on a hovered pin to resize its radius
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    const idx = findNear(pos);
    if (idx < 0) return;
    e.preventDefault();

    const delta = e.deltaY > 0 ? -0.2 : 0.2; // scroll down = shrink, up = grow
    const pin = pins[idx];
    const newRadius = Math.max(0.2, Math.min(10.0, (pin.radius ?? DEFAULT_PIN_RADIUS) + delta));
    const next = pins.map((p, i) => i === idx ? { ...p, radius: newRadius } : p);
    onPinsChange(next);
  }, [pins, findNear, getPos, onPinsChange]);

  const onContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
  }, []);

  return {
    canvasRef,
    handlers: { onMouseDown, onMouseMove, onMouseUp, onMouseLeave, onContextMenu, onWheel },
  };
}
