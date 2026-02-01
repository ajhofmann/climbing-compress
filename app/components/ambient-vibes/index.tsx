"use client";

import { useEffect, useRef } from "react";

type Mote = {
  x: number;
  y: number;
  radius: number;
  speed: number;
  drift: number;
  phase: number;
  opacity: number;
};

export function AmbientVibes() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);
  const motes = useRef<Mote[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    // very few, very subtle motes
    const count = Math.min(14, Math.floor(window.innerWidth / 100));
    motes.current = Array.from({ length: count }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      radius: 1 + Math.random() * 1.5,
      speed: 0.04 + Math.random() * 0.06,
      drift: (Math.random() - 0.5) * 0.12,
      phase: Math.random() * Math.PI * 2,
      opacity: 0.06 + Math.random() * 0.08,
    }));

    const ctx = canvas.getContext("2d")!;
    let t = 0;

    // detect dark mode
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dotColor = isDark ? "180, 160, 130" : "120, 100, 70";

    const animate = () => {
      t += 0.016;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const m of motes.current) {
        m.y -= m.speed;
        m.x += m.drift + Math.sin(t * 0.3 + m.phase) * 0.05;

        if (m.y < -10) {
          m.y = canvas.height + 10;
          m.x = Math.random() * canvas.width;
        }

        const pulse = 0.7 + 0.3 * Math.sin(t * 0.5 + m.phase);
        ctx.globalAlpha = m.opacity * pulse;
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${dotColor}, ${m.opacity * pulse})`;
        ctx.fill();
      }

      ctx.globalAlpha = 1;
      raf.current = requestAnimationFrame(animate);
    };

    raf.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(raf.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      role="presentation"
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none z-0"
    />
  );
}
