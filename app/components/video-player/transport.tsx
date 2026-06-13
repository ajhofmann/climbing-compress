"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Tooltip } from "@/components/tooltip";
import { sound } from "@/lib/sound";

function formatTimecode(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

interface TransportState {
  playing: boolean;
  muted: boolean;
  time: number;
  duration: number;
}

/**
 * Custom VCR-deck playback transport — replaces the native browser
 * <video controls> chrome with themed deck buttons, a tape-position
 * scrub bar, and live timecode readouts.
 */
export function VcrTransport({
  videoEl,
  syncEl = null,
  fps = 30,
  onOsd,
}: {
  videoEl: HTMLVideoElement | null;
  syncEl?: HTMLVideoElement | null;
  fps?: number;
  onOsd?: (label: string) => void;
}) {
  const [state, setState] = useState<TransportState>({ playing: false, muted: false, time: 0, duration: 0 });
  const scrubRef = useRef<HTMLDivElement>(null);
  const scrubbing = useRef(false);
  // Mutable mirrors of the bound elements (DOM mutation goes through refs).
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const syncRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => { videoRef.current = videoEl; }, [videoEl]);
  useEffect(() => { syncRef.current = syncEl; }, [syncEl]);

  // Bind playback listeners to the active video element.
  useEffect(() => {
    if (!videoEl) return;
    const read = () => {
      setState({
        playing: !videoEl.paused && !videoEl.ended,
        muted: videoEl.muted,
        time: videoEl.currentTime,
        duration: Number.isFinite(videoEl.duration) ? videoEl.duration : 0,
      });
    };
    read();
    const events = ["play", "pause", "ended", "timeupdate", "durationchange", "volumechange", "loadedmetadata"] as const;
    events.forEach((ev) => videoEl.addEventListener(ev, read));
    return () => events.forEach((ev) => videoEl.removeEventListener(ev, read));
  }, [videoEl]);

  const syncSeek = useCallback(() => {
    const v = videoRef.current;
    const s = syncRef.current;
    if (v && s) s.currentTime = v.currentTime;
  }, []);

  const safePlay = useCallback((el: HTMLVideoElement | null) => {
    if (!el) return;
    void el.play().catch(() => {});
  }, []);

  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      safePlay(v);
      safePlay(syncRef.current);
      onOsd?.("▶ PLAY");
    } else {
      v.pause();
      syncRef.current?.pause();
      onOsd?.("❚❚ PAUSE");
    }
  }, [safePlay, onOsd]);

  const stop = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    v.currentTime = 0;
    const s = syncRef.current;
    if (s) {
      s.pause();
      s.currentTime = 0;
    }
    onOsd?.("■ STOP");
  }, [onOsd]);

  const seekBy = useCallback((delta: number, label: string) => {
    const v = videoRef.current;
    if (!v) return;
    const duration = Number.isFinite(v.duration) ? v.duration : 0;
    v.currentTime = Math.max(0, Math.min(duration || v.currentTime + delta, v.currentTime + delta));
    syncSeek();
    onOsd?.(label);
  }, [syncSeek, onOsd]);

  const stepFrame = useCallback((direction: -1 | 1) => {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    syncRef.current?.pause();
    const frame = 1 / Math.max(1, fps);
    seekBy(direction * frame, direction > 0 ? "❚▶ STEP" : "◀❚ STEP");
  }, [fps, seekBy]);

  const toggleMute = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    onOsd?.(v.muted ? "AUDIO OFF" : "AUDIO ON");
  }, [onOsd]);

  const seekToPointer = useCallback((clientX: number) => {
    const v = videoRef.current;
    if (!v || !scrubRef.current) return;
    const rect = scrubRef.current.getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const duration = Number.isFinite(v.duration) ? v.duration : 0;
    v.currentTime = pct * duration;
    syncSeek();
  }, [syncSeek]);

  const onScrubDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    scrubbing.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    seekToPointer(e.clientX);
    sound.tick();
  }, [seekToPointer]);

  const onScrubMove = useCallback((e: React.PointerEvent) => {
    if (!scrubbing.current) return;
    seekToPointer(e.clientX);
  }, [seekToPointer]);

  const onScrubUp = useCallback(() => {
    scrubbing.current = false;
  }, []);

  const pct = state.duration > 0 ? state.time / state.duration : 0;
  const disabled = !videoEl;

  return (
    <div className="flex items-center gap-2 flex-wrap px-2 py-1.5 rounded"
      style={{
        background: "linear-gradient(180deg, #181828 0%, #10101c 100%)",
        border: "1px solid rgba(0,229,255,0.08)",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04), inset 0 -1px 0 rgba(0,0,0,0.3)",
      }}
    >
      {/* Deck buttons */}
      <div className="flex items-center gap-1">
        <Tooltip text="Rewind 5s (J = 1s)">
          <button onClick={() => seekBy(-5, "◀◀ REW")} disabled={disabled} className="vcr-btn !px-2 !py-0.5 !text-[11px]" aria-label="Rewind 5 seconds">
            ◀◀
          </button>
        </Tooltip>
        <Tooltip text="Play / pause (K or Space)">
          <button onClick={togglePlay} disabled={disabled} className="vcr-btn vcr-btn--primary !px-3 !py-0.5 !text-[11px]" aria-label={state.playing ? "Pause" : "Play"}>
            {state.playing ? "❚❚" : "▶"}
          </button>
        </Tooltip>
        <Tooltip text="Stop and rewind to start">
          <button onClick={stop} disabled={disabled} className="vcr-btn !px-2 !py-0.5 !text-[11px]" aria-label="Stop playback">
            ■
          </button>
        </Tooltip>
        <Tooltip text="Fast-forward 5s (L = 1s)">
          <button onClick={() => seekBy(5, "▶▶ FF")} disabled={disabled} className="vcr-btn !px-2 !py-0.5 !text-[11px]" aria-label="Fast-forward 5 seconds">
            ▶▶
          </button>
        </Tooltip>
        <span className="text-text-muted/20 text-xs select-none mx-0.5">│</span>
        <Tooltip text="Step one frame back (,)">
          <button onClick={() => stepFrame(-1)} disabled={disabled} className="vcr-btn !px-2 !py-0.5 !text-[11px]" aria-label="Step one frame back">
            ◀❚
          </button>
        </Tooltip>
        <Tooltip text="Step one frame forward (.)">
          <button onClick={() => stepFrame(1)} disabled={disabled} className="vcr-btn !px-2 !py-0.5 !text-[11px]" aria-label="Step one frame forward">
            ❚▶
          </button>
        </Tooltip>
      </div>

      {/* Tape position scrub bar */}
      <div
        ref={scrubRef}
        className="relative flex-1 min-w-[120px] h-[18px] cursor-pointer"
        onPointerDown={onScrubDown}
        onPointerMove={onScrubMove}
        onPointerUp={onScrubUp}
        role="slider"
        aria-label="Tape position"
        aria-valuemin={0}
        aria-valuemax={state.duration}
        aria-valuenow={state.time}
        tabIndex={0}
      >
        {/* Groove */}
        <div
          className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-[8px] rounded-sm"
          style={{
            background: "linear-gradient(180deg, #0a0a12 0%, #1a1a2e 100%)",
            border: "1px inset #222",
            boxShadow: "inset 0 1px 3px rgba(0,0,0,0.8)",
          }}
        />
        {/* Tape spooled (progress fill) */}
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-[6px] rounded-sm pointer-events-none"
          style={{
            width: `${pct * 100}%`,
            background: "linear-gradient(90deg, rgba(0,229,255,0.25), var(--neon-cyan))",
            boxShadow: "0 0 6px rgba(0,229,255,0.35)",
          }}
        />
        {/* Chrome head */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 pointer-events-none"
          style={{
            left: `${pct * 100}%`,
            width: 10,
            height: 16,
            background: "linear-gradient(180deg, #ddd 0%, #999 40%, #666 100%)",
            border: "1px outset #aaa",
            borderRadius: 2,
            boxShadow: "0 0 6px rgba(0,229,255,0.35), inset 0 1px 0 rgba(255,255,255,0.4)",
          }}
        />
      </div>

      {/* Timecode readout */}
      <span className="tape-counter text-sm whitespace-nowrap tabular-nums">
        {formatTimecode(state.time)} / {formatTimecode(state.duration)}
      </span>

      {/* Audio toggle */}
      <Tooltip text={state.muted ? "Unmute playback audio" : "Mute playback audio"}>
        <button
          onClick={toggleMute}
          disabled={disabled}
          className={`vcr-btn !px-2 !py-0.5 !text-[11px] ${state.muted ? "vcr-btn--danger" : ""}`}
          aria-label={state.muted ? "Unmute playback audio" : "Mute playback audio"}
        >
          {state.muted ? "AUD ✕" : "AUD"}
        </button>
      </Tooltip>
    </div>
  );
}

/** Flashing OSD action label that fades out — pass a new `flash` object to retrigger. */
export function OsdFlash({ flash }: { flash: { label: string; key: number } | null }) {
  if (!flash || !flash.label) return null;
  return (
    <span key={flash.key} className="vcr-osd text-lg osd-flash pointer-events-none">
      {flash.label}
    </span>
  );
}

/** Live tape-counter timecode bound to a video element (bottom OSD). */
export function LiveTimecode({ videoEl, className = "" }: { videoEl: HTMLVideoElement | null; className?: string }) {
  const [time, setTime] = useState(0);
  useEffect(() => {
    if (!videoEl) return;
    const read = () => setTime(videoEl.currentTime);
    read();
    videoEl.addEventListener("timeupdate", read);
    videoEl.addEventListener("seeked", read);
    return () => {
      videoEl.removeEventListener("timeupdate", read);
      videoEl.removeEventListener("seeked", read);
    };
  }, [videoEl]);
  return (
    <span className={`tape-counter ${className}`}>
      {formatTimecode(time)}
    </span>
  );
}
