"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CruxPoint, EditMode, Keyframe, Pin } from "@/lib/types";

interface TimelineConfig {
  duration: number;
  minSpeed: number;
  maxSpeed: number;
  curve: number[];
  curveTimes: number[];
  editMode: EditMode;
  pins: Pin[];
  keyframes: Keyframe[];
  waveformUrl: string;
  cruxPoints: CruxPoint[];
  onPinsChange: (pins: Pin[]) => void;
  onKeyframesChange: (keyframes: Keyframe[]) => void;
  trimStart: number;
  trimEnd: number;
  onTrimChange: (start: number, end: number) => void;
}

const DEFAULT_PIN_RADIUS = 2.0;

type DragTarget =
  | { type: "pin"; index: number }
  | { type: "keyframe"; index: number }
  | { type: "trim-start" }
  | { type: "trim-end" }
  | null;

export function useTimeline(config: TimelineConfig) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const waveImgRef = useRef<HTMLImageElement | null>(null);
  const [dragging, setDragging] = useState<DragTarget>(null);
  const [hoverIdx, setHoverIdx] = useState(-1);
  const [hoverTrim, setHoverTrim] = useState<"start" | "end" | null>(null);

  const {
    duration, minSpeed, maxSpeed, curve, curveTimes, editMode, pins, keyframes,
    waveformUrl, cruxPoints, onPinsChange, onKeyframesChange,
    trimStart, trimEnd, onTrimChange,
  } = config;

  const timeToX = useCallback((t: number, w: number) => (t / duration) * w, [duration]);
  const xToTime = useCallback((x: number, w: number) => Math.max(0, Math.min(duration, (x / w) * duration)), [duration]);
  const speedToY = useCallback((s: number, h: number) => h - (Math.min(s, maxSpeed) / maxSpeed) * h, [maxSpeed]);
  const yToSpeed = useCallback(
    (y: number, h: number) => Math.max(minSpeed, Math.min(maxSpeed, (1 - y / h) * maxSpeed)),
    [minSpeed, maxSpeed],
  );

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
      const n = Math.min(curve.length, curveTimes.length);
      let started = false;
      for (let i = 0; i < n; i++) {
        const cv = curve[i];
        if (cv == null || !isFinite(cv)) continue;
        const x = timeToX(curveTimes[i], w);
        const y = speedToY(cv, h);
        if (!isFinite(x) || !isFinite(y)) continue;
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      }
      if (started) ctx.stroke();
    }

    // Crux markers (backend suggestions)
    if (cruxPoints.length > 0) {
      cruxPoints.forEach((cp, idx) => {
        const x = timeToX(cp.time, w);
        if (!isFinite(x) || x < 0 || x > w) return;
        const lineAlpha = Math.max(0.25, Math.min(0.75, cp.score));
        ctx.strokeStyle = `rgba(224, 64, 251, ${lineAlpha})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();

        // Top triangle marker
        ctx.fillStyle = "rgba(224, 64, 251, 0.9)";
        ctx.beginPath();
        ctx.moveTo(x, 5);
        ctx.lineTo(x - 4, 0);
        ctx.lineTo(x + 4, 0);
        ctx.closePath();
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x, 8, 2.5, 0, Math.PI * 2);
        ctx.fill();

        const tag = `C${idx + 1}`;
        ctx.font = "bold 10px system-ui";
        const tw = ctx.measureText(tag).width;
        const lx = Math.min(Math.max(3, x - tw / 2 - 3), w - tw - 6);
        ctx.fillStyle = "rgba(24, 8, 34, 0.8)";
        ctx.beginPath();
        ctx.roundRect(lx, 10, tw + 6, 12, 3);
        ctx.fill();
        ctx.fillStyle = "#f2b8ff";
        ctx.fillText(tag, lx + 3, 19);
      });
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

    // Editable points (pins or keyframes)
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#3d5a3e";
    const warmColor = getComputedStyle(document.documentElement).getPropertyValue("--warm").trim() || "#c97b2a";
    if (editMode === "pins") {
      for (let i = 0; i < pins.length; i++) {
        const pin = pins[i];
        const x = timeToX(pin.time, w);
        const y = speedToY(pin.speed, h);
        const isHover = i === hoverIdx;
        const isDrag = dragging?.type === "pin" && dragging.index === i;
        const radiusS = pin.radius ?? DEFAULT_PIN_RADIUS;

        const radiusNorm = (radiusS - 0.2) / (10.0 - 0.2);
        const baseR = 5 + radiusNorm * 9;
        const dotR = isDrag ? baseR + 2 : isHover ? baseR + 1 : baseR;
        const glowR = dotR + 4;

        const radiusPx = timeToX(radiusS, w);
        if (radiusPx > 2) {
          const opacity = isHover || isDrag ? 0.18 : 0.06;
          const color = isDrag ? warmColor : accentColor;
          const grad = ctx.createRadialGradient(x, y, 0, x, y, radiusPx);
          grad.addColorStop(0, `${color}${Math.round(opacity * 255).toString(16).padStart(2, "0")}`);
          grad.addColorStop(1, "transparent");
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.ellipse(x, y, radiusPx, h * 0.5, 0, 0, Math.PI * 2);
          ctx.fill();
        }

        if (isHover || isDrag) {
          const rLeftX = timeToX(pin.time - radiusS, w);
          const rRightX = timeToX(pin.time + radiusS, w);
          ctx.strokeStyle = isDrag ? `${warmColor}60` : `${accentColor}35`;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 3]);
          ctx.beginPath(); ctx.moveTo(rLeftX, 0); ctx.lineTo(rLeftX, h); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(rRightX, 0); ctx.lineTo(rRightX, h); ctx.stroke();
          ctx.setLineDash([]);
        }

        ctx.beginPath();
        ctx.arc(x, y, glowR, 0, Math.PI * 2);
        ctx.fillStyle = isDrag ? `${warmColor}40` : `${accentColor}20`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, dotR, 0, Math.PI * 2);
        ctx.fillStyle = isDrag ? warmColor : accentColor;
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();

        if (isHover || isDrag) {
          const label = `${pin.speed.toFixed(1)}x @ ${pin.time.toFixed(1)}s  r=${radiusS.toFixed(1)}s`;
          ctx.font = "bold 11px system-ui";
          const tw2 = ctx.measureText(label).width;
          const lx = Math.min(x - tw2 / 2, w - tw2 - 8);
          const ly = y - dotR - 10;
          ctx.fillStyle = "rgba(0,0,0,0.75)";
          ctx.beginPath();
          const rx2 = Math.max(4, lx - 4);
          ctx.roundRect(rx2, ly - 12, tw2 + 8, 16, 4);
          ctx.fill();
          ctx.fillStyle = "#fff";
          ctx.fillText(label, Math.max(8, lx), ly);
        }
      }
    } else {
      if (keyframes.length > 1) {
        ctx.strokeStyle = "rgba(255, 214, 102, 0.9)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        keyframes.forEach((kf, idx) => {
          const x = timeToX(kf.time, w);
          const y = speedToY(kf.speed, h);
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }

      keyframes.forEach((kf, idx) => {
        const x = timeToX(kf.time, w);
        const y = speedToY(kf.speed, h);
        const isHover = idx === hoverIdx;
        const isDrag = dragging?.type === "keyframe" && dragging.index === idx;
        const size = isDrag ? 7 : isHover ? 6 : 5;

        ctx.fillStyle = isDrag ? warmColor : "#ffd666";
        ctx.beginPath();
        ctx.moveTo(x, y - size);
        ctx.lineTo(x + size, y);
        ctx.lineTo(x, y + size);
        ctx.lineTo(x - size, y);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        if (isHover || isDrag) {
          const label = `${kf.speed.toFixed(1)}x @ ${kf.time.toFixed(1)}s`;
          ctx.font = "bold 11px system-ui";
          const tw2 = ctx.measureText(label).width;
          const lx = Math.min(x - tw2 / 2, w - tw2 - 8);
          const ly = y - 16;
          ctx.fillStyle = "rgba(0,0,0,0.75)";
          ctx.beginPath();
          const rx2 = Math.max(4, lx - 4);
          ctx.roundRect(rx2, ly - 12, tw2 + 8, 16, 4);
          ctx.fill();
          ctx.fillStyle = "#fff";
          ctx.fillText(label, Math.max(8, lx), ly);
        }
      });
    }
  }, [curve, curveTimes, editMode, pins, keyframes, cruxPoints, duration, maxSpeed, hoverIdx, dragging, trimStart, trimEnd, hoverTrim, timeToX, speedToY]);

  // Load waveform image
  useEffect(() => {
    if (!waveformUrl) {
      waveImgRef.current = null;
      draw();
      return;
    }
    const img = new Image();
    img.src = waveformUrl;
    img.onload = () => {
      waveImgRef.current = img;
      draw();
    };
    waveImgRef.current = img;
  }, [waveformUrl, draw]);

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

  const findNear = useCallback((pos: { x: number; y: number }, threshold?: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return -1;
    const rect = canvas.getBoundingClientRect();
    if (editMode === "pins") {
      for (let i = 0; i < pins.length; i++) {
        const px = timeToX(pins[i].time, rect.width);
        const py = speedToY(pins[i].speed, rect.height);
        const d = Math.sqrt((pos.x - px) ** 2 + (pos.y - py) ** 2);
        const radiusS = pins[i].radius ?? DEFAULT_PIN_RADIUS;
        const radiusNorm = (radiusS - 0.2) / (10.0 - 0.2);
        const dotR = 5 + radiusNorm * 9;
        const hitR = threshold ?? Math.max(15, dotR + 6);
        if (d < hitR) return i;
      }
    } else {
      for (let i = 0; i < keyframes.length; i++) {
        const px = timeToX(keyframes[i].time, rect.width);
        const py = speedToY(keyframes[i].speed, rect.height);
        const d = Math.sqrt((pos.x - px) ** 2 + (pos.y - py) ** 2);
        const hitR = threshold ?? 14;
        if (d < hitR) return i;
      }
    }
    return -1;
  }, [editMode, pins, keyframes, timeToX, speedToY]);

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

  const maybeSnapToCrux = useCallback((t: number) => {
    if (cruxPoints.length === 0 || editMode !== "keyframes") return t;
    const SNAP_WINDOW_S = 0.18;
    let best = t;
    let bestDist = Number.POSITIVE_INFINITY;
    for (const cp of cruxPoints) {
      const d = Math.abs(cp.time - t);
      if (d < bestDist) {
        bestDist = d;
        best = cp.time;
      }
    }
    return bestDist <= SNAP_WINDOW_S ? best : t;
  }, [cruxPoints, editMode]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const pos = getPos(e);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    if (e.button === 2) {
      const idx = findNear(pos);
      if (idx >= 0) {
        if (editMode === "pins") {
          const next = pins.filter((_, j) => j !== idx);
          onPinsChange(next);
        } else {
          const next = keyframes.filter((_, j) => j !== idx);
          onKeyframesChange(next);
        }
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
      setDragging({ type: editMode === "pins" ? "pin" : "keyframe", index: idx });
    } else {
      const t = maybeSnapToCrux(xToTime(pos.x, rect.width));
      const s = yToSpeed(pos.y, rect.height);
      if (editMode === "pins") {
        const next = [...pins, { time: t, speed: s, radius: DEFAULT_PIN_RADIUS }];
        onPinsChange(next);
        setDragging({ type: "pin", index: next.length - 1 });
      } else {
        const next = [...keyframes, { time: t, speed: s }];
        onKeyframesChange(next);
      }
    }
  }, [editMode, pins, keyframes, findNear, findNearTrim, getPos, onPinsChange, onKeyframesChange, maybeSnapToCrux, xToTime, yToSpeed]);

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
        const next = pins.map((p, i) => i === dragging.index ? { ...p, time: t, speed: s } : p);
        onPinsChange(next);
      } else if (dragging.type === "keyframe") {
        const t = maybeSnapToCrux(xToTime(pos.x, rect.width));
        const s = yToSpeed(pos.y, rect.height);
        const next = keyframes.map((k, i) => i === dragging.index ? { ...k, time: t, speed: s } : k);
        onKeyframesChange(next);
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
  }, [dragging, pins, keyframes, trimStart, trimEnd, duration, findNear, findNearTrim, getPos, onPinsChange, onKeyframesChange, onTrimChange, maybeSnapToCrux, xToTime, yToSpeed]);

  const onMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  const onMouseLeave = useCallback(() => {
    setDragging(null);
    setHoverIdx(-1);
    setHoverTrim(null);
  }, []);

  // Attach wheel listener natively with { passive: false } so preventDefault()
  // actually blocks page scroll when resizing a pin's radius.
  useEffect(() => {
    if (editMode !== "pins") return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (e: WheelEvent) => {
      const rect = canvas.getBoundingClientRect();
      const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      // Use wider hit area for scroll so you don't have to be pixel-perfect
      const idx = findNear(pos, 25);
      if (idx < 0) return;
      e.preventDefault();

      // Proportional delta: trackpads give small deltaY (~1-10), mouse wheels give ~100
      // Normalize so both feel smooth — scale by current radius for natural feel
      const pin = pins[idx];
      const currentRadius = pin.radius ?? DEFAULT_PIN_RADIUS;
      const rawDelta = -e.deltaY; // positive = grow, negative = shrink
      const scaledDelta = rawDelta * 0.005 * Math.max(0.5, currentRadius * 0.3);
      const newRadius = Math.max(0.2, Math.min(10.0, currentRadius + scaledDelta));
      const next = pins.map((p, i) => i === idx ? { ...p, radius: newRadius } : p);
      onPinsChange(next);
    };

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [editMode, pins, findNear, onPinsChange]);

  // Keyboard shortcuts for hovered pin/keyframe.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (hoverIdx < 0 || dragging !== null) return;

      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || target?.isContentEditable) return;

      // Delete hovered point.
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        if (editMode === "pins") {
          const next = pins.filter((_, i) => i !== hoverIdx);
          onPinsChange(next);
        } else {
          const next = keyframes.filter((_, i) => i !== hoverIdx);
          onKeyframesChange(next);
        }
        setHoverIdx(-1);
        return;
      }

      // Arrow keys nudge hovered point with keyboard precision.
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      e.preventDefault();

      const baseTimeStep = e.shiftKey ? 0.2 : e.altKey ? 0.01 : 0.05;
      const baseSpeedStep = e.shiftKey ? 0.2 : e.altKey ? 0.01 : 0.05;
      const timeDelta = e.key === "ArrowLeft" ? -baseTimeStep : e.key === "ArrowRight" ? baseTimeStep : 0;
      const speedDelta = e.key === "ArrowDown" ? -baseSpeedStep : e.key === "ArrowUp" ? baseSpeedStep : 0;

      if (editMode === "pins") {
        const next = pins.map((pin, i) => {
          if (i !== hoverIdx) return pin;
          return {
            ...pin,
            time: Math.max(0, Math.min(duration, pin.time + timeDelta)),
            speed: Math.max(minSpeed, Math.min(maxSpeed, pin.speed + speedDelta)),
          };
        });
        onPinsChange(next);
      } else {
        const next = keyframes.map((kf, i) => {
          if (i !== hoverIdx) return kf;
          return {
            ...kf,
            time: Math.max(0, Math.min(duration, kf.time + timeDelta)),
            speed: Math.max(minSpeed, Math.min(maxSpeed, kf.speed + speedDelta)),
          };
        });
        onKeyframesChange(next);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [hoverIdx, dragging, editMode, pins, keyframes, onPinsChange, onKeyframesChange, duration, minSpeed, maxSpeed]);

  const onContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
  }, []);

  return {
    canvasRef,
    handlers: { onMouseDown, onMouseMove, onMouseUp, onMouseLeave, onContextMenu },
  };
}
