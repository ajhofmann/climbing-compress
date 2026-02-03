"use client";

import { useEffect, useRef } from "react";

type Star = {
  x: number;
  y: number;
  speed: number;
  size: number;
  color: string;
  brightness: number;
  phase: number;
};

type ShootingStar = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  color: string;
};

const NEON_COLORS = [
  "0, 229, 255",    // cyan
  "224, 64, 251",   // magenta
  "118, 255, 3",    // lime
  "255, 110, 64",   // orange
  "200, 200, 220",  // silver
];

export function AmbientVibes() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);
  const stars = useRef<Star[]>([]);
  const shootingStars = useRef<ShootingStar[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    // Create multi-layer starfield
    const count = Math.min(80, Math.floor(window.innerWidth / 15));
    stars.current = Array.from({ length: count }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      speed: 0.1 + Math.random() * 0.4,
      size: 0.5 + Math.random() * 2,
      color: NEON_COLORS[Math.floor(Math.random() * NEON_COLORS.length)],
      brightness: 0.3 + Math.random() * 0.7,
      phase: Math.random() * Math.PI * 2,
    }));

    const ctx = canvas.getContext("2d")!;
    let t = 0;
    let lastShootingSpawn = 0;

    const animate = () => {
      t += 0.016;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw stars
      for (const s of stars.current) {
        s.y -= s.speed;
        if (s.y < -5) {
          s.y = canvas.height + 5;
          s.x = Math.random() * canvas.width;
        }

        const twinkle = 0.5 + 0.5 * Math.sin(t * 2 + s.phase);
        const alpha = s.brightness * twinkle;

        // Glow
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${s.color}, ${alpha * 0.1})`;
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${s.color}, ${alpha})`;
        ctx.fill();
      }

      // Spawn shooting stars occasionally
      if (t - lastShootingSpawn > 3 + Math.random() * 5) {
        lastShootingSpawn = t;
        const color = NEON_COLORS[Math.floor(Math.random() * 3)]; // cyan/magenta/lime
        shootingStars.current.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height * 0.3,
          vx: (Math.random() - 0.3) * 6,
          vy: 2 + Math.random() * 3,
          life: 0,
          maxLife: 30 + Math.random() * 30,
          color,
        });
      }

      // Draw shooting stars
      for (let i = shootingStars.current.length - 1; i >= 0; i--) {
        const ss = shootingStars.current[i];
        ss.x += ss.vx;
        ss.y += ss.vy;
        ss.life++;

        const progress = ss.life / ss.maxLife;
        const alpha = progress < 0.3 ? progress / 0.3 : 1 - (progress - 0.3) / 0.7;

        // Trail
        ctx.beginPath();
        ctx.moveTo(ss.x, ss.y);
        ctx.lineTo(ss.x - ss.vx * 5, ss.y - ss.vy * 5);
        ctx.strokeStyle = `rgba(${ss.color}, ${alpha * 0.6})`;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Head glow
        ctx.beginPath();
        ctx.arc(ss.x, ss.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${ss.color}, ${alpha})`;
        ctx.fill();

        if (ss.life >= ss.maxLife) {
          shootingStars.current.splice(i, 1);
        }
      }

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
