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
```

Open [http://localhost:3000](http://localhost:3000), drop in a climbing video, hit **analyze**, tweak the curve, and **render**.

## Speed-ramp modes

**Constant Progress** (default) — allocates output time proportional to wall progress. At 50% of the output you're ~50% up the boulder. Rest sections are detected automatically and fast-forwarded.

**Action Highlight** — velocity-based scoring with per-limb weights. Big moves get slow-mo, chalk-ups get skipped. Classic climbing edit style.

Both modes support **pin points** — click the timeline to override the speed at any moment, with adjustable radius of influence.

## Architecture

```
server.py            FastAPI backend (upload, analyze, solve, render)
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
