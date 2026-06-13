"use client";

/**
 * SENDIT sound engine — synthesized Web Audio "hardware" sounds.
 *
 * Every sound is generated procedurally (filtered noise bursts, short
 * oscillator envelopes) so there are no audio assets to download.
 * The engine is a module-level singleton; UI components call the exported
 * play functions directly. Volume/mute persist to localStorage and are
 * exposed to React through a tiny external store (useSoundSettings).
 */

export interface SoundSettings {
  volume: number; // 0..1
  muted: boolean;
}

const STORAGE_KEY = "sendit.sound";
const DEFAULT_SETTINGS: SoundSettings = { volume: 0.5, muted: false };

function loadSettings(): SoundSettings {
  if (typeof window === "undefined") return { ...DEFAULT_SETTINGS };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw) as Partial<SoundSettings>;
    return {
      volume: typeof parsed.volume === "number" ? Math.min(1, Math.max(0, parsed.volume)) : DEFAULT_SETTINGS.volume,
      muted: typeof parsed.muted === "boolean" ? parsed.muted : DEFAULT_SETTINGS.muted,
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

type Listener = () => void;

class SoundEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private noiseBuffer: AudioBuffer | null = null;
  private motorNodes: { gain: GainNode; stop: () => void } | null = null;
  private listeners = new Set<Listener>();
  private lastTickAt = 0;

  settings: SoundSettings = loadSettings();

  // ---- React store plumbing ----
  subscribe = (fn: Listener) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getSnapshot = (): SoundSettings => this.settings;

  private commit(next: SoundSettings) {
    this.settings = next;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // localStorage unavailable — settings stay in-memory only
    }
    if (this.master && this.ctx) {
      const target = next.muted ? 0 : next.volume;
      this.master.gain.setTargetAtTime(target * target, this.ctx.currentTime, 0.02);
    }
    this.listeners.forEach((fn) => fn());
  }

  setVolume(volume: number) {
    this.commit({ ...this.settings, volume: Math.min(1, Math.max(0, volume)) });
  }
  setMuted(muted: boolean) {
    this.commit({ ...this.settings, muted });
  }

  // ---- Audio graph ----
  private ensure(): AudioContext | null {
    if (typeof window === "undefined") return null;
    if (this.settings.muted) return null;
    if (!this.ctx) {
      const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return null;
      this.ctx = new Ctor();
      this.master = this.ctx.createGain();
      const v = this.settings.muted ? 0 : this.settings.volume;
      this.master.gain.value = v * v;
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state === "suspended") {
      void this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  private getNoise(ctx: AudioContext): AudioBuffer {
    if (!this.noiseBuffer || this.noiseBuffer.sampleRate !== ctx.sampleRate) {
      const len = ctx.sampleRate; // 1s of noise, looped/offset as needed
      const buf = ctx.createBuffer(1, len, ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
      this.noiseBuffer = buf;
    }
    return this.noiseBuffer;
  }

  /** Filtered noise burst — the basis of most mechanical sounds. */
  private noiseBurst(opts: {
    at?: number;
    duration: number;
    gain: number;
    filterType?: BiquadFilterType;
    freq: number;
    q?: number;
    freqEnd?: number;
  }) {
    const ctx = this.ensure();
    if (!ctx || !this.master) return;
    const t0 = ctx.currentTime + (opts.at ?? 0);
    const src = ctx.createBufferSource();
    src.buffer = this.getNoise(ctx);
    src.loop = true;
    const filter = ctx.createBiquadFilter();
    filter.type = opts.filterType ?? "bandpass";
    filter.frequency.setValueAtTime(opts.freq, t0);
    if (opts.freqEnd && opts.freqEnd !== opts.freq) {
      filter.frequency.exponentialRampToValueAtTime(Math.max(40, opts.freqEnd), t0 + opts.duration);
    }
    filter.Q.value = opts.q ?? 1.2;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(opts.gain, t0);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + opts.duration);
    src.connect(filter).connect(gain).connect(this.master);
    src.start(t0, Math.random() * 0.5);
    src.stop(t0 + opts.duration + 0.02);
  }

  /** Short oscillator envelope — pitched components (hums, chimes, clunks). */
  private tone(opts: {
    at?: number;
    duration: number;
    gain: number;
    type?: OscillatorType;
    freq: number;
    freqEnd?: number;
  }) {
    const ctx = this.ensure();
    if (!ctx || !this.master) return;
    const t0 = ctx.currentTime + (opts.at ?? 0);
    const osc = ctx.createOscillator();
    osc.type = opts.type ?? "sine";
    osc.frequency.setValueAtTime(opts.freq, t0);
    if (opts.freqEnd && opts.freqEnd !== opts.freq) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, opts.freqEnd), t0 + opts.duration);
    }
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(opts.gain, t0 + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + opts.duration);
    osc.connect(gain).connect(this.master);
    osc.start(t0);
    osc.stop(t0 + opts.duration + 0.02);
  }

  // ---- Public sound vocabulary ----

  /** Knob/fader detent tick. Rate-limited so fast drags don't machine-gun. */
  tick() {
    const now = performance.now();
    if (now - this.lastTickAt < 28) return;
    this.lastTickAt = now;
    this.noiseBurst({ duration: 0.018, gain: 0.1, freq: 4200, q: 2.5 });
    this.tone({ duration: 0.02, gain: 0.025, type: "triangle", freq: 2600, freqEnd: 1800 });
  }

  /** Soft button press (vcr-btn, retro-btn). */
  click() {
    this.noiseBurst({ duration: 0.03, gain: 0.14, freq: 2200, q: 1.0 });
    this.tone({ duration: 0.045, gain: 0.05, type: "square", freq: 720, freqEnd: 420 });
  }

  /** Hardware toggle switch clack. */
  thunk() {
    this.noiseBurst({ duration: 0.025, gain: 0.22, freq: 1400, q: 0.9 });
    this.tone({ duration: 0.07, gain: 0.12, freq: 190, freqEnd: 85 });
  }

  /** Cassette sliding into the deck: clack → servo pull-in → seat clunk. */
  tapeInsert() {
    this.noiseBurst({ duration: 0.03, gain: 0.18, freq: 1600, q: 1.0 });
    this.noiseBurst({ at: 0.07, duration: 0.28, gain: 0.05, filterType: "lowpass", freq: 700, freqEnd: 400 });
    this.tone({ at: 0.07, duration: 0.28, gain: 0.035, type: "sawtooth", freq: 96, freqEnd: 64 });
    this.noiseBurst({ at: 0.34, duration: 0.04, gain: 0.26, freq: 900, q: 0.8 });
    this.tone({ at: 0.34, duration: 0.1, gain: 0.14, freq: 150, freqEnd: 65 });
  }

  /** Cassette eject: servo push-out → spring clack. */
  tapeEject() {
    this.noiseBurst({ duration: 0.22, gain: 0.05, filterType: "lowpass", freq: 600, freqEnd: 900 });
    this.tone({ duration: 0.22, gain: 0.03, type: "sawtooth", freq: 70, freqEnd: 110 });
    this.noiseBurst({ at: 0.22, duration: 0.035, gain: 0.22, freq: 1800, q: 1.1 });
    this.tone({ at: 0.22, duration: 0.06, gain: 0.08, freq: 240, freqEnd: 120 });
  }

  /** Heavy record-head engage clunk (render start). */
  deckEngage() {
    this.tone({ duration: 0.1, gain: 0.2, freq: 110, freqEnd: 55 });
    this.noiseBurst({ duration: 0.05, gain: 0.2, freq: 800, q: 0.7 });
    this.noiseBurst({ at: 0.09, duration: 0.05, gain: 0.12, freq: 1200, q: 0.9 });
    this.tone({ at: 0.16, duration: 0.3, gain: 0.02, type: "sawtooth", freq: 55, freqEnd: 88 });
  }

  /** Tape rewind screech (re-scan). */
  rewind() {
    this.noiseBurst({ duration: 0.45, gain: 0.06, freq: 900, freqEnd: 3200, q: 3.0 });
    this.tone({ duration: 0.45, gain: 0.02, type: "sawtooth", freq: 180, freqEnd: 700 });
  }

  /** Soft success chime (render/analysis done). */
  chime() {
    this.tone({ duration: 0.22, gain: 0.08, freq: 880 });
    this.tone({ at: 0.11, duration: 0.3, gain: 0.07, freq: 1318.5 });
  }

  /** Low error buzz. */
  buzz() {
    this.tone({ duration: 0.12, gain: 0.09, type: "square", freq: 110 });
    this.tone({ at: 0.16, duration: 0.16, gain: 0.09, type: "square", freq: 92 });
  }

  /** Start the tape-motor loop (analysis/render in progress). */
  motorStart() {
    const ctx = this.ensure();
    if (!ctx || !this.master || this.motorNodes) return;
    const t0 = ctx.currentTime;

    const src = ctx.createBufferSource();
    src.buffer = this.getNoise(ctx);
    src.loop = true;
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 750;
    const hum = ctx.createOscillator();
    hum.type = "sine";
    hum.frequency.value = 118;
    const humGain = ctx.createGain();
    humGain.gain.value = 0.35;

    // Slow wow/flutter on the motor volume
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.9;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.012;

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.04, t0 + 0.4);

    src.connect(filter).connect(gain);
    hum.connect(humGain).connect(gain);
    lfo.connect(lfoGain).connect(gain.gain);
    gain.connect(this.master);

    src.start(t0);
    hum.start(t0);
    lfo.start(t0);

    this.motorNodes = {
      gain,
      stop: () => {
        const t = ctx.currentTime;
        gain.gain.cancelScheduledValues(t);
        gain.gain.setValueAtTime(Math.max(0.0001, gain.gain.value), t);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
        src.stop(t + 0.3);
        hum.stop(t + 0.3);
        lfo.stop(t + 0.3);
      },
    };
  }

  motorStop() {
    if (!this.motorNodes) return;
    this.motorNodes.stop();
    this.motorNodes = null;
  }
}

export const sound = new SoundEngine();
