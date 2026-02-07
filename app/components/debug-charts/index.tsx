"use client";

import { useMemo, useState } from "react";
import { useStore } from "@/lib/store";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
} from "recharts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatTimePrecise(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}

function speedLabel(speed: number): string {
  if (speed <= 0.5) return "extreme slow-mo";
  if (speed <= 1.0) return "slow-mo";
  if (speed <= 1.5) return "near realtime";
  if (speed <= 3.0) return "moderate speedup";
  if (speed <= 6.0) return "fast-forward";
  return "max fast-forward";
}

// ---------------------------------------------------------------------------
// Custom tooltips
// ---------------------------------------------------------------------------

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: number;
  restRegions?: [number, number][];
}

function SpeedTooltip({ active, payload, label, restRegions }: TooltipProps) {
  if (!active || !payload?.length || label === undefined) return null;

  const speed = payload.find((p) => p.name === "speed")?.value;
  const score = payload.find((p) => p.name === "score")?.value;
  const inRest = restRegions?.some(([s, e]) => label >= s && label <= e);

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs shadow-lg backdrop-blur-sm"
      style={{
        background: "var(--bg-card-solid)",
        border: "1px solid var(--border)",
      }}
    >
      <div className="font-mono" style={{ color: "var(--text-muted)" }}>
        {formatTimePrecise(label)}
        {inRest && (
          <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300">
            REST
          </span>
        )}
      </div>
      {speed !== undefined && (
        <div className="mt-1 flex items-baseline gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: "var(--accent)" }} />
          <span style={{ color: "var(--text-muted)" }}>speed</span>
          <span className="font-mono font-semibold" style={{ color: "var(--text)" }}>
            {speed.toFixed(2)}x
          </span>
          <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
            {speedLabel(speed)}
          </span>
        </div>
      )}
      {score !== undefined && (
        <div className="flex items-baseline gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: "var(--warm)" }} />
          <span style={{ color: "var(--text-muted)" }}>score</span>
          <span className="font-mono font-semibold" style={{ color: "var(--text)" }}>
            {score.toFixed(3)}
          </span>
        </div>
      )}
    </div>
  );
}

function ScoreCompareTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length || label === undefined) return null;

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs shadow-lg backdrop-blur-sm"
      style={{
        background: "var(--bg-card-solid)",
        border: "1px solid var(--border)",
      }}
    >
      <div className="font-mono" style={{ color: "var(--text-muted)" }}>
        {formatTimePrecise(label)}
      </div>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-baseline gap-1.5 mt-0.5">
          <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: entry.color }} />
          <span style={{ color: "var(--text-muted)" }}>{entry.name}</span>
          <span className="font-mono font-semibold" style={{ color: "var(--text)" }}>
            {entry.value.toFixed(3)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart wrapper for consistent styling
// ---------------------------------------------------------------------------

function ChartSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div>
        <h3 className="text-xs font-semibold" style={{ color: "var(--text)" }}>
          {title}
        </h3>
        <p className="text-[11px] leading-relaxed mt-0.5" style={{ color: "var(--text-muted)" }}>
          {description}
        </p>
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function DebugCharts() {
  const analysis = useStore((state) => state.analysis);
  const curve = useStore((state) => state.curve);
  const curveTimes = useStore((state) => state.curveTimes);
  const solveScores = useStore((state) => state.solveScores);
  const restRegions = useStore((state) => state.restRegions);
  const settings = useStore((state) => state.settings);
  const stats = useStore((state) => state.stats);
  const playbackTime = useStore((state) => state.playbackTime);
  const [isOpen, setIsOpen] = useState(true);
  const [showComparison, setShowComparison] = useState(false);

  // Build aligned speed+score chart data
  const chartData = useMemo(() => {
    if (!curveTimes.length || !curve.length) return [];
    return curveTimes.map((t, i) => ({
      time: parseFloat(t.toFixed(2)),
      speed: curve[i] ?? 0,
      score: solveScores[i] ?? 0,
    }));
  }, [curve, curveTimes, solveScores]);

  // Map output playback time → source time for the chart tracker
  const trackerSourceTime = useMemo(() => {
    if (!curveTimes.length || !curve.length || playbackTime <= 0) return null;
    let cumOut = 0;
    for (let i = 1; i < curveTimes.length; i++) {
      const dt = curveTimes[i] - curveTimes[i - 1];
      const speed = curve[i - 1] ?? 1;
      const segOut = dt / speed;
      if (cumOut + segOut >= playbackTime) {
        const frac = (playbackTime - cumOut) / segOut;
        return curveTimes[i - 1] + frac * dt;
      }
      cumOut += segOut;
    }
    return curveTimes[curveTimes.length - 1];
  }, [curveTimes, curve, playbackTime]);

  // Build score comparison data from analysis (full video, both modes)
  const scoreCompareData = useMemo(() => {
    if (!analysis) return [];
    const progress = analysis.scores_progress;
    const action = analysis.scores_action;
    const step = analysis.scores_step;
    const fps = analysis.fps;
    return progress.map((p: number, i: number) => ({
      time: parseFloat(((i * step) / fps).toFixed(2)),
      progress: p,
      action: action[i] ?? 0,
    }));
  }, [analysis]);

  // Compute nice Y axis ticks for speed
  const speedTicks = useMemo(() => {
    if (!curve.length) return [1];
    const max = Math.max(...curve);
    const candidates = [0.25, 0.5, 1, 2, 3, 5, 8, 10, 15, 20];
    return candidates.filter((v) => v <= max * 1.2);
  }, [curve]);

  // Rest region stats
  const restStats = useMemo(() => {
    if (!restRegions.length || !analysis) return null;
    const totalRest = restRegions.reduce((sum, [s, e]) => sum + (e - s), 0);
    const duration = analysis.duration;
    return {
      count: restRegions.length,
      totalSeconds: totalRest.toFixed(1),
      percent: ((totalRest / duration) * 100).toFixed(0),
    };
  }, [restRegions, analysis]);

  if (!analysis || chartData.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      {/* Header toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-left group"
      >
        <span className="text-xs font-semibold" style={{ color: "var(--text)" }}>
          debug charts
        </span>
        <span
          className="text-[10px] transition-transform"
          style={{ color: "var(--text-muted)", transform: isOpen ? "rotate(0)" : "rotate(-90deg)" }}
        >
          ▾
        </span>
        <span className="flex-1 h-px" style={{ background: "var(--border)" }} />
        {stats && (
          <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
            {stats.speed_min}x – {stats.speed_max}x · {stats.slow_pct}% realtime
          </span>
        )}
      </button>

      {isOpen && (
        <div className="flex flex-col gap-6">
          {/* ── Chart 1: Speed Curve ── */}
          <ChartSection
            title="Speed Curve"
            description={`Speed multiplier over time (${settings.mode} mode). Above 1x = sped up, below 1x = slow-motion. ${
              restRegions.length > 0
                ? "Purple bands are detected rest sections (chalking, shaking out) that get fast-forwarded."
                : ""
            } Hover for exact values.`}
          >
            <div
              className="rounded-xl border overflow-hidden"
              style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
            >
              <ResponsiveContainer width="100%" height={320}>
                <ComposedChart data={chartData} syncId="debug" margin={{ top: 16, right: 24, bottom: 4, left: 8 }}>
                  <CartesianGrid
                    strokeDasharray="3 6"
                    stroke="var(--border)"
                    strokeOpacity={0.5}
                  />

                  {/* Rest region shading */}
                  {restRegions.map(([start, end], i) => (
                    <ReferenceArea
                      key={`rest-${i}`}
                      x1={start}
                      x2={end}
                      fill="rgba(139, 92, 246, 0.1)"
                      stroke="none"
                    />
                  ))}

                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tickFormatter={formatTime}
                    tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                    axisLine={{ stroke: "var(--border)" }}
                    tickLine={{ stroke: "var(--border)" }}
                    tickCount={10}
                  />
                  <YAxis
                    yAxisId="speed"
                    ticks={speedTicks}
                    domain={[0, "auto"]}
                    tickFormatter={(v: number) => `${v}x`}
                    tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                    axisLine={{ stroke: "var(--border)" }}
                    tickLine={{ stroke: "var(--border)" }}
                    width={42}
                    label={{
                      value: "speed",
                      angle: -90,
                      position: "insideLeft",
                      offset: 12,
                      style: { fill: "var(--text-muted)", fontSize: 10 },
                    }}
                  />
                  <YAxis
                    yAxisId="score"
                    orientation="right"
                    domain={[0, 1]}
                    tickFormatter={(v: number) => v.toFixed(1)}
                    tick={{ fill: "var(--text-muted)", fontSize: 9, opacity: 0.6 }}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                    label={{
                      value: "score",
                      angle: 90,
                      position: "insideRight",
                      offset: 10,
                      style: { fill: "var(--text-muted)", fontSize: 10, opacity: 0.6 },
                    }}
                  />

                  {/* 1x reference line */}
                  <ReferenceLine
                    yAxisId="speed"
                    y={1}
                    stroke="var(--text-muted)"
                    strokeDasharray="6 4"
                    strokeOpacity={0.5}
                    label={{
                      value: "1x realtime",
                      position: "left",
                      style: { fill: "var(--text-muted)", fontSize: 9 },
                    }}
                  />

                  {/* Playback tracker */}
                  {trackerSourceTime !== null && (
                    <ReferenceLine
                      yAxisId="speed"
                      x={parseFloat(trackerSourceTime.toFixed(2))}
                      stroke="var(--warm)"
                      strokeWidth={1.5}
                      strokeOpacity={0.8}
                    />
                  )}

                  {/* Score as subtle background area */}
                  <Area
                    yAxisId="score"
                    dataKey="score"
                    name="score"
                    fill="var(--warm)"
                    fillOpacity={0.12}
                    stroke="var(--warm)"
                    strokeWidth={1}
                    strokeOpacity={0.3}
                    type="monotone"
                    isAnimationActive={false}
                  />

                  {/* Speed curve as primary line */}
                  <Line
                    yAxisId="speed"
                    dataKey="speed"
                    name="speed"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={false}
                    type="monotone"
                    isAnimationActive={false}
                  />

                  <Tooltip
                    content={<SpeedTooltip restRegions={restRegions} />}
                    cursor={{
                      stroke: "var(--text-muted)",
                      strokeWidth: 1,
                      strokeDasharray: "4 4",
                    }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Inline stats */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
              {stats && (
                <>
                  <span>
                    slowest: <span className="font-mono font-medium" style={{ color: "var(--accent)" }}>{stats.speed_min}x</span>
                  </span>
                  <span>
                    fastest: <span className="font-mono font-medium" style={{ color: "var(--accent)" }}>{stats.speed_max}x</span>
                  </span>
                  <span>
                    output: <span className="font-mono font-medium" style={{ color: "var(--text)" }}>{stats.output_duration}s</span>
                  </span>
                  <span>
                    action/rest ratio: <span className="font-mono font-medium">{stats.action_rest_ratio}x</span>
                  </span>
                </>
              )}
              {restStats && (
                <span>
                  rest: <span className="font-mono font-medium" style={{ color: "rgb(139, 92, 246)" }}>
                    {restStats.count} sections, {restStats.totalSeconds}s ({restStats.percent}%)
                  </span>
                </span>
              )}
            </div>
          </ChartSection>

          {/* ── Chart 2: Movement Score ── */}
          <ChartSection
            title="Movement Score"
            description={
              settings.mode === "progress"
                ? "Upward wall displacement per frame. Measures how much the climber's center of mass moves toward the top. High values = active climbing. Low values = resting or readjusting. This signal determines how output time is allocated."
                : settings.mode === "action"
                  ? "Per-frame limb velocity with weighted contributions from hands, feet, and core. High values = dynamic moves that get slow-mo. Low values = stillness that gets fast-forwarded. Tweak hand/foot/core weights in settings to reshape this."
                  : "Hybrid score blends progress and action signals. Use BLEND in Program to shift from even wall progression to dynamic move emphasis."
            }
          >
            <div
              className="rounded-xl border overflow-hidden"
              style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
            >
              <ResponsiveContainer width="100%" height={200}>
                <ComposedChart data={chartData} syncId="debug" margin={{ top: 8, right: 24, bottom: 4, left: 8 }}>
                  <CartesianGrid
                    strokeDasharray="3 6"
                    stroke="var(--border)"
                    strokeOpacity={0.5}
                  />

                  {restRegions.map(([start, end], i) => (
                    <ReferenceArea
                      key={`rest-score-${i}`}
                      x1={start}
                      x2={end}
                      fill="rgba(139, 92, 246, 0.1)"
                      stroke="none"
                    />
                  ))}

                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tickFormatter={formatTime}
                    tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                    axisLine={{ stroke: "var(--border)" }}
                    tickLine={{ stroke: "var(--border)" }}
                    tickCount={10}
                  />
                  <YAxis
                    domain={[0, "auto"]}
                    tickFormatter={(v: number) => v.toFixed(2)}
                    tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                    axisLine={{ stroke: "var(--border)" }}
                    tickLine={{ stroke: "var(--border)" }}
                    width={42}
                    label={{
                      value: settings.mode === "progress" ? "displacement" : settings.mode === "action" ? "velocity" : "hybrid",
                      angle: -90,
                      position: "insideLeft",
                      offset: 12,
                      style: { fill: "var(--text-muted)", fontSize: 10 },
                    }}
                  />

                  {/* Playback tracker */}
                  {trackerSourceTime !== null && (
                    <ReferenceLine
                      x={parseFloat(trackerSourceTime.toFixed(2))}
                      stroke="var(--warm)"
                      strokeWidth={1.5}
                      strokeOpacity={0.8}
                    />
                  )}

                  <Area
                    dataKey="score"
                    name={settings.mode === "progress" ? "progress" : settings.mode === "action" ? "action" : "hybrid"}
                    fill="var(--warm)"
                    fillOpacity={0.25}
                    stroke="var(--warm)"
                    strokeWidth={1.5}
                    type="monotone"
                    isAnimationActive={false}
                  />

                  <Tooltip
                    content={<ScoreCompareTooltip />}
                    cursor={{
                      stroke: "var(--text-muted)",
                      strokeWidth: 1,
                      strokeDasharray: "4 4",
                    }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </ChartSection>

          {/* ── Chart 3: Mode Comparison (collapsible) ── */}
          {scoreCompareData.length > 0 && (
            <div className="flex flex-col gap-2">
              <button
                onClick={() => setShowComparison(!showComparison)}
                className="flex items-center gap-2 text-left"
              >
                <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                  mode comparison
                </span>
                <span
                  className="text-[10px] transition-transform"
                  style={{ color: "var(--text-muted)", transform: showComparison ? "rotate(0)" : "rotate(-90deg)" }}
                >
                  ▾
                </span>
                <span className="flex-1 h-px" style={{ background: "var(--border)", opacity: 0.5 }} />
              </button>

              {showComparison && (
                <ChartSection
                  title="Progress vs Action Scores"
                  description="Side-by-side comparison of both scoring modes across the full (untrimmed) video. Progress scoring emphasizes steady upward displacement — good for tracking wall position. Action scoring emphasizes explosive limb velocity — good for highlighting dynamic moves. Use this to understand how switching modes changes the speed curve shape."
                >
                  <div
                    className="rounded-xl border overflow-hidden"
                    style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
                  >
                    <ResponsiveContainer width="100%" height={200}>
                      <ComposedChart data={scoreCompareData} margin={{ top: 8, right: 24, bottom: 4, left: 8 }}>
                        <CartesianGrid
                          strokeDasharray="3 6"
                          stroke="var(--border)"
                          strokeOpacity={0.5}
                        />
                        <XAxis
                          dataKey="time"
                          type="number"
                          domain={["dataMin", "dataMax"]}
                          tickFormatter={formatTime}
                          tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                          axisLine={{ stroke: "var(--border)" }}
                          tickLine={{ stroke: "var(--border)" }}
                          tickCount={10}
                        />
                        <YAxis
                          domain={[0, "auto"]}
                          tickFormatter={(v: number) => v.toFixed(2)}
                          tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                          axisLine={{ stroke: "var(--border)" }}
                          tickLine={{ stroke: "var(--border)" }}
                          width={42}
                          label={{
                            value: "score",
                            angle: -90,
                            position: "insideLeft",
                            offset: 12,
                            style: { fill: "var(--text-muted)", fontSize: 10 },
                          }}
                        />

                        <Area
                          dataKey="progress"
                          name="progress"
                          fill="var(--accent)"
                          fillOpacity={0.15}
                          stroke="var(--accent)"
                          strokeWidth={1.5}
                          type="monotone"
                          isAnimationActive={false}
                        />
                        <Area
                          dataKey="action"
                          name="action"
                          fill="var(--warm)"
                          fillOpacity={0.15}
                          stroke="var(--warm)"
                          strokeWidth={1.5}
                          type="monotone"
                          isAnimationActive={false}
                        />

                        <Tooltip
                          content={<ScoreCompareTooltip />}
                          cursor={{
                            stroke: "var(--text-muted)",
                            strokeWidth: 1,
                            strokeDasharray: "4 4",
                          }}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Legend */}
                  <div className="flex gap-4 px-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-0.5 rounded-full inline-block" style={{ background: "var(--accent)" }} />
                      progress — upward wall displacement
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-0.5 rounded-full inline-block" style={{ background: "var(--warm)" }} />
                      action — limb velocity
                    </span>
                  </div>
                </ChartSection>
              )}
            </div>
          )}

          {/* ── Tuning guide ── */}
          <details className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
            <summary className="cursor-pointer font-medium text-xs" style={{ color: "var(--text-muted)" }}>
              tuning guide
            </summary>
            <div className="mt-2 flex flex-col gap-2 pl-3 border-l-2" style={{ borderColor: "var(--border)" }}>
              <p>
                <strong style={{ color: "var(--text)" }}>Speed too uniform?</strong>{" "}
                Increase <em>steepness</em> to widen the gap between fast and slow sections.
                Lower <em>smoothing</em> for sharper transitions.
              </p>
              <p>
                <strong style={{ color: "var(--text)" }}>Rest sections not detected?</strong>{" "}
                Lower <em>rest threshold</em> to catch shorter pauses. The purple bands in the chart
                show what the algorithm considers resting.
              </p>
              <p>
                <strong style={{ color: "var(--text)" }}>Moves not getting enough slow-mo?</strong>{" "}
                In action mode, increase <em>hand/foot/core weights</em> for the limbs that matter.
                In progress mode, increase <em>vertical bias</em> to focus on upward movement.
              </p>
              <p>
                <strong style={{ color: "var(--text)" }}>Output too long/short?</strong>{" "}
                Adjust <em>target duration</em>. The solver will redistribute speeds within
                min/max bounds to hit your target.
              </p>
              <p>
                <strong style={{ color: "var(--text)" }}>Need surgical control?</strong>{" "}
                Click the speed curve editor above to add pin points. Each pin pulls the speed
                toward a fixed value with adjustable radius. Scroll to resize a pin&apos;s influence zone.
              </p>
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
