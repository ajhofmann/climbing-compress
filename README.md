# climb-ramp

Automatic speed-ramping for climbing videos. Upload a send, and climb-ramp slows down the moves and fast-forwards the rest -- so 50% through the video means 50% up the boulder.

<!-- TODO: add a before/after GIF or video of an outdoor climbing send here -->
<!-- ![demo](docs/demo.gif) -->

## How it works

1. **Upload** a climbing video
2. **Analyze** -- MediaPipe detects the climber's pose in every frame, scores movement vs rest, and tracks vertical progress
3. **Tweak** the speed curve in the interactive timeline editor (or use a preset)
4. **Render** -- FFmpeg outputs the speed-ramped video with optional stabilization, audio time-stretch, and chapter overlays

<!-- TODO: add a screenshot of the UI with a speed curve loaded here -->
<!-- ![ui](docs/ui.png) -->

## Quickstart

```bash
# backend
pip install -e .

# frontend
cd app && npm install
```

Requires Python 3.9+, Node.js 18+, and [FFmpeg](https://ffmpeg.org/) on your `PATH`.

Optional person tracking (YOLO + ByteTrack):
```bash
pip install -e ".[tracking]"
```

## Usage

```bash
# terminal 1: API server
python server.py

# terminal 2: frontend
cd app && npm run dev
```

Open [http://localhost:3000](http://localhost:3000), drop in a video, hit **Analyze**, tweak the curve, and **Render**.

## Speed-ramp modes

- **Constant Progress** (default) -- output time proportional to wall progress. Rest is auto-detected and fast-forwarded.
- **Action Highlight** -- velocity-based scoring with per-limb weights. Big moves get slow-mo, chalk-ups get skipped.
- **Hybrid** -- blends progress and action curves with a dedicated blend control.

## Architecture

```
server.py              FastAPI (upload, analyze, solve, render)
pipeline/
  pose.py              MediaPipe pose detection + sanitization
  movement.py          Movement & progress scoring
  speed_curve.py       Speed curve solvers (action/progress/hybrid)
  render.py            FFmpeg decode/encode + audio time-stretch
  stabilize.py         Pose-anchored + feature-based stabilization
  flow.py              Optical flow / camera motion estimation
  tracker.py           YOLOv8 + ByteTrack person tracking (optional)
  cache.py             Content-hash caching
app/                   Next.js frontend
  components/          Timeline editor, settings, video player, upload
  lib/                 API client, Zustand store, types
```

## More

- [Detailed features, keyboard shortcuts, and filter reference](docs/FEATURES.md)
- [Contributing](CONTRIBUTING.md)
- [License](LICENSE) (MIT)
