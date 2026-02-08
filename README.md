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
- Upload panel includes a **Recent** row so you can reload local clips without reopening the file picker.
- Recent entries now keep a friendly upload filename (instead of only hash IDs), and backend video metadata is cached for faster repeat loads.
- Re-uploading identical content updates the friendly display name (useful for quick local renaming without duplicate files).
- Loaded clip bar now includes an **EJECT** action to jump back to the dropzone/recent picker without refreshing the page.
- Loaded clip bar also includes **DELETE** to remove the currently loaded clip from local library in one step.
- Loaded clip bar surfaces the active clip filename for easier confirmation before delete/swap actions.
- Loaded clip bar includes **RENAME** for quick relabeling of local clips.
- Loaded clip bar includes **CLEAR LIB** to wipe the entire local library without ejecting first.
- Recent entries include **✎** (rename) and **X** (delete) actions to manage local library entries in-place.
- Rename keeps supported video extensions (`.mov/.mp4/.avi/.mkv`) and auto-appends the current extension if omitted.
- Rename inputs are validated client-side before request (empty/too-long/unsupported names are rejected immediately).
- Rename no-ops are ignored (if normalized target name matches current name).
- Recent section now remains visible when empty (`no local clips`) and includes a manual `[refresh]` control.
- Recent section includes `[clear all]` to wipe the local library in one step.
- Recent section shows compact preview with overflow controls (`[show all]` / `[show less]`) when clips exceed six.
- Recent section includes quick name filtering (`filter clips`) with explicit `no matching clips` state.
- Missing/deleted source files are auto-pruned from Recent/library indexes during list refreshes.
- Refresh control now shows a temporary loading state while rescanning local clips.
- Recent header now includes a live clip count (`Recent (N)`).
- Recent header now also shows aggregated local duration (`Recent (N · M:SS)`).
- Dropzone now surfaces local-library action feedback inline (rename/delete/clear outcomes).

## Speed-ramp modes

**Constant Progress** (default) — allocates output time proportional to wall progress. At 50% of the output you're ~50% up the boulder. Rest sections are detected automatically and fast-forwarded.

**Action Highlight** — velocity-based scoring with per-limb weights. Big moves get slow-mo, chalk-ups get skipped. Classic climbing edit style.

**Hybrid** — blends progress pacing and action highlighting with a dedicated blend control.

## Editing controls

The timeline supports two edit modes:

- **Pins** — point overrides with adjustable influence radius (scroll to resize).
- **Pins (numeric panel)** — direct `time / speed / radius` inputs for precision tweaks.
- **Keyframes** — explicit speed envelope points with direct numeric editing.
- **Crux quick-fill** — in both pins and keyframes mode, `from crux` auto-seeds edits from detected crux markers.
- **Mode conversion** — `from pins` and `from keyframes` let you switch editing style without rebuilding curves.
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
