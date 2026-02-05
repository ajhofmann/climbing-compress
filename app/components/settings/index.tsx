"use client";

import { useStore } from "@/lib/store";
import { Settings } from "@/lib/types";
import { Knob } from "@/components/knob";
import { LedCounter } from "@/components/controls/led-counter";
import { Fader } from "@/components/controls/fader";
import { ToggleSwitch } from "@/components/controls/toggle-switch";
import { RotarySelect } from "@/components/controls/rotary-select";
import { MiniScope } from "@/components/controls/mini-scope";
import { BodyMap } from "@/components/controls/body-map";
import { Tooltip } from "@/components/tooltip";

function Module({ area, label, children }: { area: string; label: string; children: React.ReactNode }) {
  return (
    <div className="dashboard-module" style={{ gridArea: area }}>
      <div className="dashboard-module-label">
        <span>{label}</span>
      </div>
      <div className="dashboard-module-body">
        {children}
      </div>
    </div>
  );
}

export function SettingsPanel() {
  const store = useStore();
  const { settings, updateSettings, stats, analysis } = store;
  const s = settings;
  const u = (k: keyof Settings, v: Settings[keyof Settings]) => updateSettings({ [k]: v });

  return (
    <div className="retro-panel rounded overflow-hidden">
      {/* Dashboard Grid */}
      <div className="dashboard-grid">
        {/* ═══ PROGRAM ═══ */}
        <Module area="program" label="Program">
          <div className="flex items-start gap-3 flex-wrap">
            {/* Mode selector */}
            <div className="flex flex-col items-center gap-1">
              <span className="rack-section-label">MODE</span>
              <div className="flex flex-col gap-0 retro-inset rounded overflow-hidden" style={{ background: "#080810" }}>
                {([
                  { key: "progress" as const, label: "PROGRESS", tip: "50% of video = 50% up the wall.\nStalling = fast-forward." },
                  { key: "action" as const, label: "ACTION", tip: "Big moves get slow-mo,\nchalk-ups get skipped." },
                ]).map(({ key, label, tip }) => (
                  <Tooltip key={key} text={tip}>
                    <button
                      onClick={() => u("mode", key)}
                      className={`px-3 py-1.5 text-xs font-pixel uppercase tracking-wider transition-all ${
                        s.mode === key
                          ? "bg-gradient-to-r from-[#003844] to-[#005f6b] text-neon-cyan"
                          : "text-text-muted hover:text-text"
                      }`}
                      style={s.mode === key ? { textShadow: "0 0 6px rgba(0,229,255,0.4)", boxShadow: "inset 0 0 8px rgba(0,229,255,0.08)" } : {}}
                    >
                      {label}
                    </button>
                  </Tooltip>
                ))}
              </div>
            </div>

            {/* Duration -- Nixie tubes */}
            <LedCounter label="DURATION" value={s.targetDuration} min={3} max={120} step={1} onChange={(v) => u("targetDuration", v)} title="Target output duration in seconds.\nThe speed curve stretches to hit this." />

            {/* Speed faders */}
            {s.mode === "action" && (
              <Fader label="SENS" value={s.sensitivity} min={0.01} max={0.99} step={0.01} onChange={(v) => u("sensitivity", v)} title="Sensitivity: lower = more generous slow-mo on moves" />
            )}
            <Fader label="MAX" value={s.maxSpeed} min={1} max={30} step={0.5} onChange={(v) => u("maxSpeed", v)} color="#76ff03" title="Max Speed: how fast to skip through rest and chalk-ups" />

            {/* Analysis quality */}
            <div className="flex items-center gap-1 ml-auto" style={{ borderLeft: "1px solid #222", paddingLeft: 12 }}>
              <RotarySelect
                label="QUAL"
                value={s.analyzeStride}
                options={[
                  { value: 1, label: "HI" },
                  { value: 2, label: "BAL" },
                  { value: 3, label: "LO" },
                ]}
                onChange={(v) => u("analyzeStride", v)}
                title="Detection quality: HI = every frame, BAL = every 2nd, LO = every 3rd"
              />
              <ToggleSwitch label="TRK" checked={s.useTracker} onChange={(v) => u("useTracker", v)} color="#76ff03" title="Person tracking: YOLO + ByteTrack to isolate the climber" />
              {s.useTracker && (
                <RotarySelect
                  label="MODEL"
                  value={s.trackerModel}
                  options={[
                    { value: "yolo26n", label: "FAST" },
                    { value: "yolo26s", label: "BAL" },
                    { value: "yolo26m", label: "ACC" },
                  ]}
                  onChange={(v) => u("trackerModel", v)}
                  title="Tracker model: FAST = yolo26n (quick), BAL = yolo26s (balanced), ACC = yolo26m (most accurate)"
                />
              )}
              <ToggleSwitch label="FLOW" checked={s.useFlow} onChange={(v) => u("useFlow", v)} color="#e040fb" title="Optical flow + shake compensation from wall features" />
            </div>
          </div>
        </Module>

        {/* ═══ STATUS ═══ */}
        <Module area="status" label="Status">
          <div className="flex flex-col gap-2">
            {/* Mini scope */}
            <MiniScope />

            {/* Stats readouts */}
            {stats ? (
              <div className="grid grid-cols-2 gap-1">
                {[
                  { label: "OUT", value: `${stats.output_duration}s`, tip: "Output video duration" },
                  { label: "SPD", value: `${stats.speed_min}x-${stats.speed_max}x`, tip: "Speed range (min to max playback speed)" },
                  { label: "RATIO", value: `${stats.action_rest_ratio}x`, tip: "Ratio of action to rest segments" },
                  { label: "RT", value: `${stats.slow_pct}%`, tip: "Percentage of output in slow motion" },
                ].map(({ label, value, tip }) => (
                  <Tooltip key={label} text={tip}>
                    <div className="retro-inset rounded px-1.5 py-0.5 text-center" style={{ background: "#080810" }}>
                      <span className="text-xs text-text-muted font-pixel">{label} </span>
                      <span className="text-xs font-retro led-text">{value}</span>
                    </div>
                  </Tooltip>
                ))}
              </div>
            ) : (
              <div className="retro-inset rounded px-2 py-2 text-center" style={{ background: "#080810" }}>
                <span className="text-xs font-pixel text-text-muted">AWAITING DATA</span>
              </div>
            )}

            {/* Feature pilot lights */}
            {analysis && (
              <div className="flex gap-2 justify-center flex-wrap">
                {analysis.tracker_available && (
                  <Tooltip text="Person tracker data is available">
                    <span className="flex items-center gap-1 text-[11px] font-pixel text-neon-lime uppercase">
                      <span className="pilot-light pilot-light-green pilot-light-breathe" />TRK
                    </span>
                  </Tooltip>
                )}
                {analysis.flow_available && (
                  <Tooltip text="Optical flow data is available">
                    <span className="flex items-center gap-1 text-[11px] font-pixel text-neon-magenta uppercase">
                      <span className="pilot-light pilot-light-magenta pilot-light-breathe" />FLW
                    </span>
                  </Tooltip>
                )}
                {analysis.camera_motion_available && (
                  <Tooltip text="Camera shake data is available">
                    <span className="flex items-center gap-1 text-[11px] font-pixel text-neon-orange uppercase">
                      <span className="pilot-light pilot-light-orange pilot-light-breathe" />SHK
                    </span>
                  </Tooltip>
                )}
              </div>
            )}
          </div>
        </Module>

        {/* ═══ MIXER (body map or faders) ═══ */}
        <Module area="mixer" label={s.mode === "action" ? "Weights" : "Speed"}>
          {s.mode === "action" ? (
            <BodyMap
              handWeight={s.handWeight}
              footWeight={s.footWeight}
              coreWeight={s.coreWeight}
              onHandChange={(v) => u("handWeight", v)}
              onFootChange={(v) => u("footWeight", v)}
              onCoreChange={(v) => u("coreWeight", v)}
            />
          ) : (
            <div className="flex gap-2 justify-center">
              <Fader label="V-BIAS" value={s.verticalBias} min={0} max={1} step={0.05} onChange={(v) => u("verticalBias", v)} color="#00e5ff" title="Vertical Bias: 0.5 = equal weight, 1.0 = vertical movement only" />
              <Fader label="DOWN" value={s.downWeight} min={0} max={1} step={0.05} onChange={(v) => u("downWeight", v)} color="#e040fb" title="Down Weight: 0 = ignore downclimbing, 1 = count it equally" />
              <Fader label="REST" value={s.restThreshold} min={0} max={2} step={0.05} onChange={(v) => u("restThreshold", v)} color="#ff6e40" title="Rest Skip: seconds of stillness before fast-forwarding" />
            </div>
          )}
        </Module>

        {/* ═══ TUNE ═══ */}
        <Module area="tune" label="Tune">
          <div className="flex gap-2 flex-wrap justify-center">
            <Knob label="Smooth" info="Seconds of curve blur -- higher = smoother transitions" value={s.smoothing} min={0.05} max={2} step={0.05} onChange={(v) => u("smoothing", v)} />
            <Knob label="Min Spd" info="Slowest allowed speed (0.05 = 20x slow-mo)" value={s.minSpeed} min={0.05} max={1} step={0.01} onChange={(v) => u("minSpeed", v)} />
            {s.mode === "action" && (
              <Knob label="Steep" info="Steepness of speed transitions -- higher = sharper" value={s.steepness} min={1} max={50} step={1} onChange={(v) => u("steepness", v)} />
            )}
            {s.mode === "progress" && (
              <Knob label="P.Floor" info="Minimum progress rate even during rest" value={s.progressFloor} min={0} max={0.2} step={0.005} onChange={(v) => u("progressFloor", v)} />
            )}
          </div>
        </Module>

        {/* ═══ OUTPUT ═══ */}
        <Module area="output" label="Output">
          <div className="flex gap-2 flex-wrap items-start">
            <Knob label="Res" info="Output resolution scale: 0.25 = tiny preview, 1.0 = full res" value={s.scale} min={0.1} max={1} step={0.05} onChange={(v) => u("scale", v)} />
            <Knob label="CRF" info="Encoding quality: lower = sharper but bigger file" value={s.crf} min={10} max={40} step={1} onChange={(v) => u("crf", v)} />
            <RotarySelect
              label="FPS"
              value={s.outputFps}
              options={[
                { value: 24, label: "24" },
                { value: 30, label: "30" },
                { value: 60, label: "60" },
              ]}
              onChange={(v) => u("outputFps", v)}
              title="Output frame rate: 24 = cinematic, 30 = standard, 60 = smooth"
            />
          </div>
        </Module>

      </div>

      {/* ═══ OPTIONS — full-width strip below grid ═══ */}
      <div className="dashboard-module">
        <div className="dashboard-module-label">
          <span>Options</span>
        </div>
        <div className="dashboard-module-body">
          <div className="flex items-start gap-4 flex-wrap">
            <ToggleSwitch label="AUD" checked={s.includeAudio} onChange={(v) => u("includeAudio", v)} title="Include time-stretched audio from source" />
            <ToggleSwitch label="OVL" checked={s.debugOverlay} onChange={(v) => u("debugOverlay", v)} color="#76ff03" title="Show skeleton + speed badge overlay on video" />
            <ToggleSwitch label="A/B" checked={s.renderComparison} onChange={(v) => u("renderComparison", v)} color="#e040fb" title="Also render a uniform-speed version for comparison" />
            <ToggleSwitch label="STAB" checked={s.stabilize} onChange={(v) => u("stabilize", v)} color="#ff6e40" title="Enable pose-anchored video stabilization" />
            {s.stabilize && (
              <>
                <Knob label="Str" info="Stabilize strength: 0 = off, 1 = full gimbal lock" value={s.stabilizeStrength} min={0} max={1} step={0.01} onChange={(v) => u("stabilizeStrength", v)} />
                <Knob label="Smth" info="Trajectory smoothing in seconds" value={s.stabilizeSmoothness} min={0.1} max={5} step={0.1} onChange={(v) => u("stabilizeSmoothness", v)} />
                <Knob label="Crop" info="Frame border sacrificed for shake room" value={s.stabilizeCrop} min={0.01} max={0.5} step={0.01} onChange={(v) => u("stabilizeCrop", v)} />
                <ToggleSwitch label="FEAT" checked={s.useFeatureStabilize} onChange={(v) => u("useFeatureStabilize", v)} color="#e040fb" title="Blend feature-based camera motion estimation" />
                {s.useFeatureStabilize && (
                  <Knob label="F.Wt" info="Feature weight: 0 = pose only, 1 = features only" value={s.featureStabilizeWeight} min={0} max={1} step={0.05} onChange={(v) => u("featureStabilizeWeight", v)} />
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Signal flow SVG overlay (decorative) */}
      <svg className="w-full h-[2px] opacity-50" viewBox="0 0 800 2" preserveAspectRatio="none">
        <line x1="0" y1="1" x2="800" y2="1" className="signal-flow-line" />
        <circle r="2" className="signal-flow-dot">
          <animateMotion dur="3s" repeatCount="indefinite" path="M0,1 L800,1" />
        </circle>
        <circle r="2" className="signal-flow-dot" style={{ animationDelay: "1.5s" }}>
          <animateMotion dur="3s" repeatCount="indefinite" path="M0,1 L800,1" begin="1.5s" />
        </circle>
      </svg>
    </div>
  );
}
