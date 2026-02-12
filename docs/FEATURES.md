# Features

Detailed feature reference for climb-ramp. For quickstart and overview, see the root [README](../README.md).

## Upload and clip management

- Supported file extensions: `.mov`, `.mp4`, `.avi`, `.mkv`
- Backend upload cap defaults to `512 MB` (override with `MAX_UPLOAD_MB`)
- **Recent** panel for one-click reload of local clips
- Content-dedup: re-uploading identical video reuses the same clip ID
- Loaded clip toolbar includes **SWAP**, **EJECT**, **RENAME**, **DELETE**, **CLEAR OUT**, **CLEAR LIB**, and **PREV/NEXT** navigation
- Per-clip and library-wide storage/output stats shown inline

## Speed-ramp modes

**Constant Progress** (default) -- allocates output time proportional to wall progress. At 50% of the output you're ~50% up the boulder. Rest sections are detected automatically and fast-forwarded.

**Action Highlight** -- velocity-based scoring with per-limb weights. Big moves get slow-mo, chalk-ups get skipped. Classic climbing edit style.

**Hybrid** -- blends progress pacing and action highlighting with a dedicated blend control.

## Timeline editing

The timeline supports two edit modes:

- **Pins** -- point overrides with adjustable influence radius (scroll to resize)
- **Pins (numeric panel)** -- direct `time / speed / radius` inputs for precision tweaks
- **Keyframes** -- explicit speed envelope points with direct numeric editing
- **Crux quick-fill** -- in both modes, `from crux` auto-seeds edits from detected crux markers
- **Mode conversion** -- `from pins` and `from keyframes` let you switch editing style without rebuilding curves
- **Point ordering tools** -- `sort pins` / `sort keyframes` re-normalize timeline point order after numeric edits
- Keyboard precision shortcuts on hovered points:
  - `Delete` / `Backspace` remove hovered pin/keyframe
  - Arrow keys nudge time/speed (`Shift` = larger step, `Alt` = fine step)
  - `[` / `]` resize hovered pin radius (`Shift` = larger step, `Alt` = fine step)

The solver also returns **crux markers** (`C1`, `C2`, ...) on the timeline. In keyframe mode, points can snap to nearby crux markers for fast alignment.

## Output workflows

- **Quick Preview** button for fast local iterations (draft render settings, no audio)
- Full **Render** for final quality output
- Cancel active render from the transport bar or press `Esc`
- Optional **Chapter overlays** (`START`, `CRUX`, `SEND`) on rendered output
- Style templates (`Cinematic`, `Coaching`, `Social Vertical`) for one-click tuning
- Output **aspect control** (`original`, `9:16`, `1:1`) plus optional **auto-reframe** to follow the climber when cropping

## Keyboard shortcuts

### Transport

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + Shift + A` | Analyze / Cancel Analyze |
| `Ctrl/Cmd + Enter` | Quick Preview |
| `Ctrl/Cmd + Shift + Enter` | Full Render |
| `Esc` | Cancel active render |

### Playback (when output player is visible)

| Shortcut | Action |
|----------|--------|
| `K` or `Space` | Play / Pause |
| `J` / `L` | Seek -1s / +1s |
| `,` / `.` | Frame-step backward / forward |

### Clip management

| Shortcut | Action |
|----------|--------|
| `Alt + P` / `Alt + N` | Previous / next clip |
| `Alt + X` | Eject current clip |
| `Ctrl/Cmd + Shift + O` | Clear outputs (global or clip-specific) |

### Dropzone mode

| Shortcut | Action |
|----------|--------|
| `/` | Focus recent filter |
| `O` | Cycle output-scope filter |
| `C` | Cycle cache-scope filter |
| `S` | Cycle sort mode |
| `D` | Toggle sort reversal |
| `R` | Refresh recent clips |
| `V` | Reset view filters |
| `A` | Toggle show all / show less |
| `1`-`0` | Load clip by slot number |
| `?` | Toggle shortcut help |

## Recent clip filtering

The recent panel supports a powerful filter query syntax with space-separated AND matching:

### Simple tags

`#cached`, `#uncached`, `#out`, `#noout`, `#short`, `#long`, `#portrait`, `#landscape`, `#square`

Prefix with `-` or `!` to exclude (e.g. `-#out`, `!#cached`). Prefix with `+` for explicit include.

### Comparator tags

| Family | Examples |
|--------|----------|
| Output count | `#out>=1`, `#out=0`, `#out!=0`, `#out=0..2` |
| Source bytes | `#src>3k`, `#src>10m`, `#src=2k..4k` |
| Output bytes | `#mb>0b`, `#mb>1mb` |
| Duration | `#dur>5`, `#dur>90s`, `#dur>1m30s`, `#dur=1..2` |
| FPS | `#fps>=24`, `#fps=24..60` |
| Width/Height | `#w>=1080`, `#h>=1080` |
| Aspect ratio | `#ar>=1.3`, `#ar=1.3..1.8`, `#ar>=16:9` |
| Frame count | `#fc<=30`, `#fc=25..200` |
| Pixel area | `#px>=2mp`, `#px=1mp..3mp` |
| Resolution | `#res=1920x1080`, `#res>=1920x1080` |
| Extension | `#ext=mp4`, `#ext=mp4,mov`, `#ext*=mp` |
| Filename | `#name=clip.mp4`, `#name*=clip` |
| Video ID | `#id*=abc`, `#id=abc123,def456` |

Ranges use `..` syntax with optional open ends: `#dur=..2` (up to 2s), `#src=2k..` (at least 2KB).

Long-form aliases are supported (e.g. `#duration`, `#framerate`, `#resolution`, `#filename`).

Typos are auto-detected with "did you mean" suggestions and one-click repair.
