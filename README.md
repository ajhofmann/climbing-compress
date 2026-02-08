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
- Loaded/recent delete feedback now reports rendered-output cleanup counts when matching outputs were removed.
- Loaded clip bar surfaces the active clip filename for easier confirmation before delete/swap actions.
- Loaded clip bar includes **RENAME** for quick relabeling of local clips.
- Loaded clip bar includes **CLEAR LIB** to wipe the entire local library without ejecting first.
- Loaded clip bar includes **CLEAR OUT** to purge rendered outputs for the loaded clip only.
- Loaded clip bar includes **PREV/NEXT** to cycle recent clips in-place (wrap-around) without ejecting.
- Loaded clip bar now shows `out:clip/total` (`out:C/T`) near clip metadata for per-clip vs global output visibility.
- Loaded clip bar now also shows source storage footprint (`src:clip/total`) for current-clip vs library-size context.
- Loaded clip bar also shows output storage footprint (`mb:clip/total`) for quick disk-usage checks.
- Loaded `out:C/T` counter now auto-refreshes after quick/full renders and clip deletion flows (no manual refresh needed).
- Upload/load metadata now carries per-clip `output_count` so loaded counters hydrate immediately on open/reuse.
- Loaded `[CLEAR OUT]` is disabled when current clip has no render outputs (`out:0/T`), even if other clips still have outputs.
- Loaded **SWAP** action is disabled while analyze/render/library-mutation jobs are active to prevent conflicting state changes.
- Recent entries include **✎** (rename) and **X** (delete) actions to manage local library entries in-place.
- Rename keeps supported video extensions (`.mov/.mp4/.avi/.mkv`) and auto-appends the current extension if omitted.
- Rename inputs are validated client-side before request (empty/too-long/unsupported names are rejected immediately).
- Rename no-ops are ignored (if normalized target name matches current name).
- Recent section now remains visible when empty (`no local clips`) and includes a manual `[refresh]` control.
- Recent section includes `[clear all]` to wipe the local library in one step.
- Recent section shows `[clear filtered]` only when a subset filter is active; it deletes only currently filtered clips (name/output/cache scopes respected).
- `[clear filtered]` confirmation uses live per-clip output stats, so rendered-output counts/sizes stay accurate even if outputs changed on disk.
- Recent section includes `[clear filt out]` to remove only rendered outputs from the current filtered subset (keeps source clips).
- `[clear all]` / `CLEAR LIB` now also remove rendered output files and report both counts in status feedback.
- Recent section now includes `[clear outputs]` for global output-only cleanup while keeping local source clips.
- Recent controls now show live render-output counter (`out:N`) and disable output cleanup when `out:0`.
- Recent controls now show compact output storage (`mb:X`) next to `out:N`.
- Recent controls now also show compact source-library storage (`lib:X`) for quick local disk checks.
- When any subset filter is active (name/output/cache), Recent header also shows filtered-view storage/output summary (`view:* · out:* · mb:*`).
- Output-clear confirmations now include count + size summaries (for example: `2 rendered outputs, 12 B`).
- Delete/clear status feedback now includes freed source/output byte sizes when available.
- Recent/output counters remain accurate after loaded-clip deletes (no stale double-decrement drift).
- Each Recent clip row now includes a mini output-clear action (`◍`) for clip-scoped render cleanup without loading the clip first.
- Recent mini output-clear action (`◍`) is now clip-aware and disabled when that specific clip has zero rendered outputs.
- Recent mini output-clear action now displays clip output count inline (`◍N`) when outputs exist.
- Keyboard: `Ctrl/Cmd + Shift + O` triggers output cleanup (global in dropzone, clip-specific when a clip is loaded).
- Keyboard: `Ctrl/Cmd + Alt + O` clears outputs for the current filtered subset in dropzone mode.
- Keyboard: `Alt + P` / `Alt + N` cycle previous/next recent clip from loaded mode.
- Keyboard: `Alt + X` ejects the currently loaded clip back to dropzone mode.
- Recent section shows compact preview with overflow controls (`[show all]` / `[show less]`) when clips exceed six.
- Recent section includes quick name filtering (`filter clips`) with explicit `no matching clips` state, space-separated AND matching, and `-term` exclusions.
- Recent filter now renders active term chips (`+term` includes, `-term` excludes) to clarify parsed query semantics.
- Recent section includes output-scope filtering (`[out:all]` / `[out:with]` / `[out:none]`) for output-housekeeping workflows.
- Output-scope toggle now shows scope counts inline (`[out:all:N]`, `[out:with:N]`, `[out:none:N]`) for quick triage.
- Recent section also includes cache-scope filtering (`[cache:all]` / `[cache:cached]` / `[cache:uncached]`) for warm/cold analysis triage.
- Scope counters are contextual: `out:*:N` reflects active cache scope and `cache:*:N` reflects active output scope.
- Press `O` in dropzone mode to cycle output-scope filters (`all -> with -> none -> all`).
- Press `C` in dropzone mode to cycle cache-scope filters (`all -> cached -> uncached -> all`).
- Press `S` in dropzone mode to cycle Recent sort modes (`recent -> name -> duration -> outputs -> size`).
- Press `D` in dropzone mode to toggle Recent sort reversal (`[rev:off]` / `[rev:on]`).
- Press `R` in dropzone mode to refresh Recent clips + output counters without clicking `[refresh]`.
- Press `V` in dropzone mode (or click `[reset view]`) to clear name/output/cache subset filters back to all.
- Press `Shift + V` in dropzone mode (or click `[reset all]`) to restore full Recent view defaults (sort, reverse, filters, expansion, keys help).
- Press `A` in dropzone mode to toggle recent preview expansion (`[show all]` / `[show less]`) when overflow exists.
- Press `1-0` in dropzone mode to load matching visible recent clip slots instantly (`0` targets slot 10).
- Press `?` (Shift + `/`) in dropzone mode (or click `[keys:on/off]`) to toggle shortcut help text.
- `[keys:on/off]` shortcut-help visibility persists across reloads with other Recent view preferences.
- Press `/` in dropzone mode to focus the recent clip filter instantly.
- Press `Esc` to clear an active recent filter and restore unfiltered preview.
- Press `Enter` in the recent filter input to load the first matching clip instantly.
- Press `↑` / `↓` in the recent filter input to choose a clip (wraps at list ends), then `Enter` to load the highlighted selection.
- Selected keyboard target is shown with a `▶` prefix in the recent clip row.
- Recent clip row now shows `1-0` slot markers for quick keyboard loading (`0` marker = slot 10).
- Recent filter text now persists across reloads (alongside sort/show/scope preferences).
- Missing/deleted source files are auto-pruned from Recent/library indexes during list refreshes.
- Refresh control now shows a temporary loading state while rescanning local clips.
- Recent header now includes a live clip count (`Recent (N)`).
- Recent header now also shows aggregated local duration (`Recent (N · M:SS)`).
- While filtering, Recent header switches to filtered/total metrics (`Recent (n/N · m:ss/M:SS)`).
- Dropzone now surfaces local-library action feedback inline (rename/delete/clear outcomes).
- Recent row now supports sort cycling (`[sort:recent]`, `[sort:name]`, `[sort:duration]`, `[sort:outputs]`, `[sort:size]`).
- Recent sort mode, reverse state, and expansion preferences persist across page reloads for faster local iteration.

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
- **Point ordering tools** — `sort pins` / `sort keyframes` re-normalize timeline point order after numeric edits.
- Keyboard precision shortcuts on hovered points:
  - `Delete` / `Backspace` remove hovered pin/keyframe
  - Arrow keys nudge time/speed (`Shift` = larger step, `Alt` = fine step)
  - `[` / `]` resize hovered pin radius (`Shift` = larger step, `Alt` = fine step)

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
