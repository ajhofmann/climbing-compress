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
cp .env.example .env  # edit if needed

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

# Optional: start the background worker
python worker.py
```

Open [http://localhost:3000](http://localhost:3000), drop in a climbing video, hit **analyze**, tweak the curve, and **render**.

## Background jobs (optional)

The API now records analyze/render/preview jobs in SQLite. You can run work
in-process (default) or queue jobs for a background worker:

```bash
# Start the worker loop (executes queued jobs)
python worker.py
```

To enqueue jobs without running them on the API thread, call:

- `POST /api/jobs/analyze?run_background=false`
- `POST /api/jobs/render?run_background=false`
- `POST /api/jobs/preview?run_background=false`

Use `POST /api/jobs/{job_id}/cancel` to cancel queued/running work.

### UI queue mode

Enable the **QUEUE** toggle in the Options strip to run analyze/render/preview
via background jobs. The UI will poll job status instead of relying on SSE.

## Speed-ramp modes

**Constant Progress** (default) — allocates output time proportional to wall progress. At 50% of the output you're ~50% up the boulder. Rest sections are detected automatically and fast-forwarded.

**Action** — velocity-based scoring with per-limb weights. Big moves get slow-mo, chalk-ups get skipped. Classic climbing edit style.

**Highlight** — blend of action + progress for crux-heavy highlight reels.

Both modes support **pin points** — click the timeline to override the speed at any moment, with adjustable radius of influence.

## Architecture

```
server.py            FastAPI backend (upload, analyze, solve, render, jobs)
worker.py            Background job worker (polls SQLite queue)
pipeline/
  pose.py            MediaPipe pose detection + sanitization
  movement.py        Movement & progress scoring
  speed_curve.py     Speed curve solvers (action + progress modes)
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
