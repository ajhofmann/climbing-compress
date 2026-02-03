"use client";

import { useEffect, useRef } from "react";

const H = 180;
const STAR_COUNT = 70;

type Star = { x: number; y: number; r: number; phase: number; speed: number };

function createStars(w: number, h: number): Star[] {
  return Array.from({ length: STAR_COUNT }, () => ({
    x: Math.random() * w,
    y: Math.random() * h * 0.52,
    r: Math.random() * 1.2 + 0.3,
    phase: Math.random() * Math.PI * 2,
    speed: Math.random() * 2 + 0.5,
  }));
}

/* ---- drawing helpers ---- */

function drawBg(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#030308");
  g.addColorStop(0.42, "#08081a");
  g.addColorStop(0.55, "#0c0820");
  g.addColorStop(1, "#0a0a14");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

function drawStars(ctx: CanvasRenderingContext2D, stars: Star[], t: number) {
  for (const s of stars) {
    const b = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase));
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(180, 200, 255, ${b * 0.7})`;
    ctx.fill();
    if (s.r > 1) {
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r * 3, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(100, 180, 255, ${b * 0.08})`;
      ctx.fill();
    }
  }
}

function drawSun(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  const cx = w / 2;
  const cy = h * 0.5;
  const r = Math.min(w * 0.11, 78);
  const pulse = 1 + Math.sin(t * 0.5) * 0.015;

  // outer glow
  ctx.save();
  const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 3);
  glow.addColorStop(0, "rgba(255, 140, 50, 0.12)");
  glow.addColorStop(0.4, "rgba(255, 50, 120, 0.05)");
  glow.addColorStop(1, "transparent");
  ctx.fillStyle = glow;
  ctx.fillRect(0, cy - r * 3, w, r * 6);
  ctx.restore();

  // clip to circle
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, r * pulse, 0, Math.PI * 2);
  ctx.clip();

  // gradient fill
  const grad = ctx.createLinearGradient(cx, cy - r, cx, cy + r);
  grad.addColorStop(0, "#ffee58");
  grad.addColorStop(0.25, "#ffab00");
  grad.addColorStop(0.5, "#ff4081");
  grad.addColorStop(0.8, "#d500f9");
  grad.addColorStop(1, "#7c4dff");
  ctx.fillStyle = grad;
  ctx.fillRect(cx - r - 1, cy - r - 1, r * 2 + 2, r * 2 + 2);

  // synthwave horizontal stripe cutouts (bottom half)
  ctx.fillStyle = "#030308";
  const stripeCount = 8;
  for (let i = 0; i < stripeCount; i++) {
    const frac = i / stripeCount;
    if (frac < 0.45) continue;
    const y = cy + (frac - 0.45) * r * 2 * (1 / 0.55);
    const gap = 1.5 + (frac - 0.45) * 9;
    ctx.fillRect(cx - r - 1, y, r * 2 + 2, gap);
  }
  ctx.restore();
}

function drawMountainLayer(
  ctx: CanvasRenderingContext2D,
  w: number,
  baseY: number,
  peaks: [number, number][],
  maxH: number,
  fillColor: string,
  edgeColor: string,
  glowSize: number,
) {
  // fill
  ctx.beginPath();
  ctx.moveTo(0, baseY);
  for (const [xf, hf] of peaks) ctx.lineTo(xf * w, baseY - hf * maxH);
  ctx.lineTo(w, baseY);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();

  // neon edge
  ctx.beginPath();
  ctx.moveTo(0, baseY);
  for (const [xf, hf] of peaks) ctx.lineTo(xf * w, baseY - hf * maxH);
  ctx.lineTo(w, baseY);
  ctx.save();
  ctx.shadowBlur = glowSize;
  ctx.shadowColor = edgeColor;
  ctx.strokeStyle = edgeColor;
  ctx.lineWidth = 1.2;
  ctx.stroke();
  ctx.restore();
}

function drawMountains(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const horizon = h * 0.54;
  const maxH1 = h * 0.26;
  const maxH2 = h * 0.16;

  // back range (taller, cyan glow)
  drawMountainLayer(
    ctx, w, horizon,
    [
      [0, 0.05], [0.06, 0.32], [0.11, 0.52], [0.16, 0.28],
      [0.22, 0.68], [0.28, 0.38], [0.34, 0.78], [0.39, 0.48],
      [0.44, 0.35], [0.50, 0.55], [0.56, 0.88], [0.61, 0.45],
      [0.66, 0.32], [0.72, 0.62], [0.78, 0.38], [0.84, 0.55],
      [0.90, 0.28], [0.95, 0.42], [1, 0.1],
    ],
    maxH1, "#04040c", "rgba(0, 229, 255, 0.3)", 8,
  );

  // front range (shorter, magenta glow)
  drawMountainLayer(
    ctx, w, horizon + 6,
    [
      [0, 0.04], [0.08, 0.22], [0.15, 0.42], [0.22, 0.14],
      [0.30, 0.38], [0.37, 0.55], [0.44, 0.18], [0.52, 0.48],
      [0.58, 0.28], [0.65, 0.52], [0.72, 0.22], [0.78, 0.38],
      [0.85, 0.12], [0.92, 0.30], [1, 0.06],
    ],
    maxH2, "#06060e", "rgba(224, 64, 251, 0.2)", 6,
  );
}

function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  const vpx = w / 2;
  const horizon = h * 0.55;
  const gridLines = 22;
  const vertLines = 30;
  const scrollOffset = (t * 0.25) % 1;

  // sun reflection on ground
  const refl = ctx.createLinearGradient(vpx, horizon, vpx, h);
  refl.addColorStop(0, "rgba(255, 100, 50, 0.04)");
  refl.addColorStop(0.4, "rgba(200, 50, 200, 0.02)");
  refl.addColorStop(1, "transparent");
  ctx.fillStyle = refl;
  ctx.fillRect(vpx - w * 0.3, horizon, w * 0.6, h - horizon);

  // horizontal
  for (let i = 0; i < gridLines; i++) {
    const rawFrac = (i + scrollOffset) / gridLines;
    const frac = Math.pow(rawFrac, 2.2);
    const y = horizon + (h - horizon) * frac;
    const spread = 0.04 + rawFrac * 0.96;
    const x1 = vpx - w * 0.55 * spread;
    const x2 = vpx + w * 0.55 * spread;
    const alpha = Math.min(rawFrac * 3, 1) * 0.3;

    ctx.beginPath();
    ctx.moveTo(x1, y);
    ctx.lineTo(x2, y);
    ctx.strokeStyle = `rgba(0, 229, 255, ${alpha})`;
    ctx.lineWidth = rawFrac > 0.6 ? 1 : 0.5;
    ctx.stroke();
  }

  // vertical
  for (let i = -vertLines / 2; i <= vertLines / 2; i++) {
    const frac = i / (vertLines / 2);
    const topX = vpx + frac * w * 0.02;
    const bottomX = vpx + frac * w * 0.55;
    const alpha = 0.18 * (1 - Math.abs(frac) * 0.5);

    ctx.beginPath();
    ctx.moveTo(topX, horizon);
    ctx.lineTo(bottomX, h);
    ctx.strokeStyle = `rgba(0, 229, 255, ${alpha})`;
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  // horizon glow
  const hGlow = ctx.createLinearGradient(0, horizon - 4, 0, horizon + 6);
  hGlow.addColorStop(0, "transparent");
  hGlow.addColorStop(0.5, "rgba(0, 229, 255, 0.15)");
  hGlow.addColorStop(1, "transparent");
  ctx.fillStyle = hGlow;
  ctx.fillRect(0, horizon - 4, w, 10);
}

function drawSideCircuits(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  const lineLen = w * 0.12;

  for (let side = 0; side < 2; side++) {
    const isRight = side === 1;
    for (let i = 0; i < 3; i++) {
      const y = h * 0.22 + i * 16;
      const len = lineLen * (1 - i * 0.3);
      const alpha = 0.12 + 0.04 * Math.sin(t * 2 + i + side);
      const x0 = isRight ? w : 0;
      const x1 = isRight ? w - len : len;

      ctx.beginPath();
      ctx.moveTo(x0, y);
      ctx.lineTo(x1, y);
      ctx.strokeStyle = `rgba(0, 229, 255, ${alpha})`;
      ctx.lineWidth = 0.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x1, y, 1.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 229, 255, ${alpha * 1.8})`;
      ctx.fill();
    }
  }
}

function drawScanLine(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  const scanY = ((t * 28) % (h + 40)) - 20;
  const sg = ctx.createLinearGradient(0, scanY - 18, 0, scanY + 18);
  sg.addColorStop(0, "transparent");
  sg.addColorStop(0.5, "rgba(0, 229, 255, 0.05)");
  sg.addColorStop(1, "transparent");
  ctx.fillStyle = sg;
  ctx.fillRect(0, scanY - 18, w, 36);
}

function drawVignette(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const vg = ctx.createRadialGradient(w / 2, h / 2, w * 0.28, w / 2, h / 2, w * 0.72);
  vg.addColorStop(0, "transparent");
  vg.addColorStop(1, "rgba(0, 0, 0, 0.45)");
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, w, h);
}

function drawNoise(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.fillStyle = "rgba(255, 255, 255, 0.015)";
  for (let i = 0; i < 20; i++) {
    ctx.fillRect(Math.random() * w, Math.random() * h, 1, 1);
  }
}

function drawGlitch(ctx: CanvasRenderingContext2D, w: number, h: number) {
  if (Math.random() > 0.025) return;
  const y = Math.random() * h;
  const gh = Math.random() * 3 + 1;
  ctx.fillStyle = `rgba(0, 229, 255, ${Math.random() * 0.08})`;
  ctx.fillRect(0, y, w, gh);
}

/* ---- component ---- */

export function HeaderArt() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const rafRef = useRef(0);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext("2d")!;

    const fit = () => {
      const dpr = window.devicePixelRatio || 1;
      const { width } = cvs.getBoundingClientRect();
      cvs.width = width * dpr;
      cvs.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      starsRef.current = createStars(width, H);
    };
    fit();
    window.addEventListener("resize", fit);

    let t = 0;
    const loop = () => {
      t += 0.016;
      const w = cvs.getBoundingClientRect().width;
      const h = H;

      drawBg(ctx, w, h);
      drawStars(ctx, starsRef.current, t);
      drawSun(ctx, w, h, t);
      drawMountains(ctx, w, h);
      drawGrid(ctx, w, h, t);
      drawSideCircuits(ctx, w, h, t);
      drawScanLine(ctx, w, h, t);
      drawNoise(ctx, w, h);
      drawGlitch(ctx, w, h);
      drawVignette(ctx, w, h);

      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", fit);
    };
  }, []);

  return (
    <div className="relative w-full overflow-hidden" style={{ height: H, borderRadius: 6 }}>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ borderRadius: 6 }}
      />

      {/* neon border */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          borderRadius: 6,
          border: "1px solid rgba(0, 229, 255, 0.1)",
          boxShadow:
            "inset 0 0 40px rgba(0, 229, 255, 0.03), 0 0 20px rgba(0, 229, 255, 0.05)",
        }}
      />

      {/* corner brackets */}
      <svg className="absolute top-2 left-2" width="22" height="22" style={{ opacity: 0.25 }}>
        <polyline points="0,16 0,0 16,0" stroke="#00e5ff" strokeWidth="1" fill="none" />
        <circle cx="1" cy="1" r="1" fill="#00e5ff" />
      </svg>
      <svg className="absolute top-2 right-2" width="22" height="22" style={{ opacity: 0.25 }}>
        <polyline points="22,16 22,0 6,0" stroke="#00e5ff" strokeWidth="1" fill="none" />
        <circle cx="21" cy="1" r="1" fill="#00e5ff" />
      </svg>
      <svg className="absolute bottom-2 left-2" width="22" height="22" style={{ opacity: 0.2 }}>
        <polyline points="0,6 0,22 16,22" stroke="#e040fb" strokeWidth="1" fill="none" />
        <circle cx="1" cy="21" r="1" fill="#e040fb" />
      </svg>
      <svg className="absolute bottom-2 right-2" width="22" height="22" style={{ opacity: 0.2 }}>
        <polyline points="22,6 22,22 6,22" stroke="#e040fb" strokeWidth="1" fill="none" />
        <circle cx="21" cy="21" r="1" fill="#e040fb" />
      </svg>

      {/* status indicators */}
      <div className="absolute top-3 left-5 flex items-center gap-2 z-10">
        <span className="pilot-light pilot-light-green pilot-light-breathe" />
        <span className="font-pixel text-[7px] tracking-[0.15em] opacity-35" style={{ color: "var(--chrome-dark)" }}>
          SYS.ONLINE
        </span>
      </div>
      <div className="absolute top-3 right-5 flex items-center gap-2 z-10">
        <span className="font-pixel text-[7px] tracking-[0.15em] opacity-35" style={{ color: "var(--chrome-dark)" }}>
          v2.0
        </span>
        <span className="pilot-light pilot-light-cyan pilot-light-breathe" />
      </div>

      {/* title overlay */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none select-none"
        style={{ paddingBottom: "6%" }}
      >
        <h1 className="font-pixel text-3xl md:text-5xl lg:text-[3.5rem] tracking-[0.15em] text-white header-title-glow">
          SENDIT
        </h1>

        <div className="flex items-center gap-3 mt-4">
          <div
            className="h-px w-10 md:w-20"
            style={{
              background: "linear-gradient(90deg, transparent, rgba(0,229,255,0.4))",
            }}
          />
          <p
            className="font-pixel text-[8px] md:text-[10px] tracking-[0.22em] uppercase"
            style={{
              color: "var(--neon-cyan)",
              opacity: 0.65,
              textShadow: "0 0 10px rgba(0,229,255,0.4)",
            }}
          >
            Speed Ramp System
          </p>
          <div
            className="h-px w-10 md:w-20"
            style={{
              background: "linear-gradient(270deg, transparent, rgba(0,229,255,0.4))",
            }}
          />
        </div>

        <p
          className="font-retro text-sm tracking-[0.3em] mt-2"
          style={{ color: "var(--chrome-dark)", opacity: 0.4 }}
        >
          CLIMB HARDER
        </p>
      </div>
    </div>
  );
}
