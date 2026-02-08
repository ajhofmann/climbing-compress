# climb-ramp

Automatic speed-ramping for climbing videos. Upload a send, and climb-ramp will slow down the moves and fast-forward the rest — so 50% through the video means 50% up the boulder.

FastAPI backend (pose detection, movement scoring, FFmpeg rendering) + Next.js frontend with an interactive speed curve editor.

## Prerequisites

- Python 3.9+
- Node.js 18+
- [FFmpeg](https://ffmpeg.org/) on your `PATH`

Optional (for person tracking):
```
pip install climb-ramp[tracking]
```

## Setup

```bash
# Backend
pip install -e .

# Frontend
cd app
npm install
```

## Usage

```bash
# Start the API server
python server.py

# In another terminal, start the frontend
cd app
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), drop in a climbing video, hit **analyze**, tweak the curve, and **render**.

Upload notes:
- Supported file extensions: `.mov`, `.mp4`, `.avi`, `.mkv`
- Backend upload cap defaults to `512 MB` (override with `MAX_UPLOAD_MB`)

## Speed-ramp modes

**Constant Progress** (default) — allocates output time proportional to wall progress. At 50% of the output you're ~50% up the boulder. Rest sections are detected automatically and fast-forwarded.

**Action Highlight** — velocity-based scoring with per-limb weights. Big moves get slow-mo, chalk-ups get skipped. Classic climbing edit style.

**Hybrid** — blends progress pacing and action highlighting with a dedicated blend control.

## Editing controls

The timeline supports two edit modes:

- **Pins** — point overrides with adjustable influence radius (scroll to resize).
- **Keyframes** — explicit speed envelope points with direct numeric editing.
- Keyboard precision shortcuts on hovered points:
  - `Delete` / `Backspace` remove hovered pin/keyframe
  - Arrow keys nudge time/speed (`Shift` = larger step, `Alt` = fine step)

The solver also returns **crux markers** (`C1`, `C2`, …) on the timeline. In keyframe mode, points can snap to nearby crux markers for fast alignment.

## Output workflows

- **Quick Preview** button for fast local iterations (draft render settings, no audio).
- Full **Render** for final quality output.
- You can cancel an active render from the transport bar (or press `Esc` while rendering).
- Keyboard transport shortcuts:
  - `Ctrl/Cmd + Shift + A` → Analyze / Cancel Analyze
  - `Ctrl/Cmd + Enter` → Quick Preview
  - `Ctrl/Cmd + Shift + Enter` → Full Render
- Playback shortcuts (when output player is visible):
  - `K` (or `Space`) → Play / Pause
  - `J` / `L` → Seek -1s / +1s
  - `,` / `.` → frame-step backward / forward (uses output FPS step)
- Optional **Chapter overlays** (`START`, `CRUX`, `SEND`) on rendered output.
- Style templates in the UI (`Cinematic`, `Coaching`, `Social Vertical`) for one-click tuning.
- Output **aspect control** (`original`, `9:16`, `1:1`) plus optional **auto-reframe** to follow the climber when cropping vertical/square exports.

## Architecture

```
server.py            FastAPI backend (upload, analyze, solve, render)
pipeline/
  pose.py            MediaPipe pose detection + sanitization
  movement.py        Movement & progress scoring
  speed_curve.py     Speed curve solvers (action/progress/hybrid + keyframes)
  render.py          FFmpeg decode/encode with stabilization + audio
  stabilize.py       Pose-anchored + feature-based stabilization
  flow.py            Optical flow / camera motion estimation
  tracker.py         YOLOv8 + ByteTrack person tracking (optional)
  cache.py           Content-hash caching
  smooth.py          One Euro Filter for temporal smoothing
  debug_overlay.py   Skeleton + speed badge overlays
utils/
  video_io.py        Video I/O helpers
  viz.py             Waveform rendering + thumbnails
app/                 Next.js frontend
  components/        Timeline editor, settings, video player, upload
  lib/               API client, Zustand store, types
```
