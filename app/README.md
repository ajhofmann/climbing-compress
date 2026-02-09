# Frontend (Next.js app)

UI for climb-ramp: video upload, analysis controls, timeline editing, and render playback.

## Local development

From this directory:

```bash
npm install
npm run dev
```

App runs on [http://localhost:3000](http://localhost:3000).

By default, the frontend calls the backend at `http://localhost:8000`.
Override with:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Upload constraints are enforced by the backend:
- accepted extensions: `.mov`, `.mp4`, `.avi`, `.mkv`
- default max file size: `512 MB` (via backend `MAX_UPLOAD_MB`)
- the no-video dropzone also shows a **Recent** list for one-click reload of local clips
- recent items preserve human-readable upload names and load faster on repeat (server-side metadata cache)
- dedup re-uploads reuse the same clip id but refresh the displayed filename
- loaded clip toolbar includes `[EJECT]` for returning to the dropzone + Recent list without reloading
- loaded clip toolbar includes `[DELETE]` to remove the active clip from local library
- delete feedback now includes rendered-output cleanup counts when related outputs are removed
- loaded clip toolbar displays active filename to clarify swap/delete actions
- loaded clip toolbar includes `[RENAME]` to relabel the active clip
- loaded clip toolbar includes `[CLEAR LIB]` to wipe all local clips immediately
- loaded clip toolbar includes `[CLEAR OUT]` to purge rendered outputs for the loaded clip only
- loaded clip toolbar includes `[PREV]` / `[NEXT]` to cycle clips in-place (wrap-around) using current Recent view when filters/sort are active
- loaded clip toolbar shows `[nav:view]` / `[nav:all]` to indicate adjacent-navigation source scope
- loaded clip toolbar shows `out:C/T` (clip/global output counts) near clip metadata for quick housekeeping visibility
- loaded clip toolbar shows `src:C/T` (current clip bytes / total library bytes) for local-storage context
- loaded clip toolbar also shows `mb:C/T` (clip/global output bytes) for local disk-usage awareness
- loaded `out:C/T` count auto-refreshes after quick/full renders and loaded-clip deletion flows
- upload/load metadata now includes per-clip `output_count` so loaded counters hydrate immediately
- loaded `[CLEAR OUT]` is disabled when clip output count is zero (`out:0/T`)
- loaded `[SWAP]` is guarded/disabled during analyze, render, and library mutation operations
- each recent pill has `✎` (rename) and `X` (delete) actions for local library cleanup
- rename actions preserve allowed video extensions and auto-append current extension when omitted
- rename actions are prevalidated client-side (length + extension) before API submission
- no-op renames are skipped when normalized target equals current filename
- recent module shows explicit empty state (`no local clips`) and a `[refresh]` action to rescan local library
- recent module includes `[clear all]` action for one-click local library wipe
- recent module only shows `[clear filtered]` when a subset filter is active; it deletes clips matching active name/output/cache filters
- `[clear filtered]` confirm pulls live per-clip output stats before prompt so output counts/sizes are accurate
- recent module includes `[clear filt out]` to clear rendered outputs for only the active filtered subset (source clips kept)
- clear-library actions now also purge rendered outputs and include both clip/output counts in feedback
- recent module includes `[clear outputs]` for global output-only cleanup while keeping local clips
- recent controls display live `out:N` render-output count and disable output cleanup when `out:0`
- recent controls display compact output storage (`mb:X`) beside `out:N`
- recent controls also display compact source-library storage (`lib:X`) beside output counters
- recent header shows filtered-view summary (`view:* · out:* · mb:*`) whenever name/output/cache subset filtering is active
- clear-output confirms include output count + size summaries before deleting renders
- delete/clear status messages now include freed source/output sizes where available
- recent/library output count remains consistent after loaded delete operations (no extra decrement drift)
- recent clip rows include a mini output-clear action (`◍`) for per-clip render cleanup directly from dropzone
- recent mini output-clear action (`◍`) is clip-aware and disabled when that clip has no outputs
- recent mini output-clear action shows inline per-clip output count (`◍N`) when available
- recent output-scope toggle cycles all/with/none output presence filters for dropzone triage
- output-scope toggle displays matching clip counts inline (`out:all:N`, `out:with:N`, `out:none:N`)
- recent cache-scope toggle cycles all/cached/uncached analysis-state filters with inline counts
- scope counts are contextual (`out:*:N` respects active cache scope, `cache:*:N` respects active output scope)
- keyboard `O` cycles output-scope filters in dropzone mode (`all -> with -> none`)
- keyboard `C` cycles cache-scope filters in dropzone mode (`all -> cached -> uncached`)
- keyboard `S` cycles recent sort modes in dropzone (`recent -> name -> duration -> outputs -> size`)
- keyboard `D` toggles recent sort reversal (`[rev:off]` / `[rev:on]`)
- keyboard `R` refreshes recent clips + output counts in dropzone mode without clicking `[refresh]`
- keyboard `V` (or `[reset view]`) resets name/output/cache subset filters back to default all-state
- keyboard `Shift+V` (or `[reset all]`) restores full Recent defaults (sort/reverse/filter/expansion/keys-help)
- keyboard `A` toggles recent preview expansion between `[show all]` and `[show less]` when overflow exists
- keyboard `Z` toggles zero-match quick tag visibility (`[+N zero]` / `[hide 0s]`)
- number keys `1-0` in dropzone load corresponding visible recent clip slots (`0` loads slot 10)
- `?` (Shift + `/`) or `[keys:on/off]` toggles inline dropzone shortcut help text
- `[keys:on/off]` help visibility state persists across reloads with Recent preferences
- keyboard shortcut `Ctrl/Cmd + Shift + O` clears outputs contextually (global in dropzone, clip-only in loaded toolbar)
- keyboard shortcut `Ctrl/Cmd + Alt + O` clears outputs for the active filtered subset in dropzone
- keyboard shortcuts `Alt+P` / `Alt+N` cycle previous/next loaded clip using current `[nav:*]` scope
- keyboard shortcut `Alt+X` ejects the loaded clip back to the dropzone selector
- recent module supports overflow expansion (`[show all]` / `[show less]`) beyond six clip previews
- recent module supports inline name filtering with dedicated `no matching clips` empty state, space-separated AND-term matching, quoted phrase terms (e.g. `"alpha beta"`), explicit `+term` includes, and `-term` / `!term` exclusions
- filter query also supports metadata tags: `#cached`, `#uncached`, `#out`, `#noout`, `#short`, `#long`, `#portrait`, `#landscape`, `#square` (plus exclusions like `-#out` or `!#out`), with simple-tag aliases like `#cache/#warm` -> `#cached` and `#nocache/#cold` -> `#uncached`
- includes can also be prefixed explicitly with `+` (e.g. `+#cached` or `+"alpha beta"`)
- quoted phrases also work for exclude prefixes and comparator values (e.g. `!"alpha beta"` and `#name="my clip.mp4"`)
- output-count comparators are supported too (e.g. `#out>=1`, `#out=0`, `#out!=0`, `#out>2`), including alias `#outputs...`
- comparator ranges are supported using `..`, including open-ended bounds (e.g. `#out=0..2`, `#src=2k..4k`, `#dur=1..2`, `#dur=..2`, `#src=2k..`)
- comparator equality accepts both `=` and `==` forms (e.g. `#out==0`, `#dur==8`)
- comparator typo aliases are accepted (`=>` as `>=`, `=<` as `<=`, `<>` as `!=`)
- storage comparators are supported with byte units (e.g. `#src>3k`, `#src>3kb`, `#src>3kib`, `#src!=3k`, `#src>10m`, `#mb>0b`, `#mb>1mb`, `#mb>1mib`), including aliases `#source...` / `#sourcebytes...` (source bytes) and `#render...` / `#outputbytes...` (render-output bytes)
- duration comparator tags are supported too (e.g. `#dur>5`, `#dur<2`, `#dur<=1.5`, `#dur!=5`, `#dur>90s`, `#dur>1m30s`, `#dur>1.5m`, `#dur>1:30`, `#dur>0:00:01.8`, `#dur>1h2m`), including aliases `#time...` and `#duration...`
- video metadata comparators are supported for fps/width/height/aspect/frame-count/resolution too (e.g. `#fps<=24`, `#fps=24..60`, `#w=..1080`, `#h>=1080`, `#ar=1.3..1.8`, `#ar>=16:9`, `#fc<=30`, `#res=1920x1080`), including long aliases `#framerate...`, `#width...`, `#height...`, `#aspect...`, `#ratio...`, `#frames...`, and `#resolution...`
- resolution comparators accept separators `x`, `×`, `*`, or `:` (e.g. `#res=1920x1080`, `#res=1920*1080`, `#res=16:9`)
- extension comparators are supported as equality checks too (e.g. `#ext=mp4`, `#ext=mp4,mov`, `#ext!=mov`), including long alias `#format...`
- filename comparators are supported as exact/pattern checks too (e.g. `#name=clip.mp4`, `#name=clip.mp4,other.mp4`, `#name!=clip.mp4`, `#name*=clip`, `#name^=recent_`, `#name$=.mp4`), including aliases `#file...` and `#filename...`
- video-id comparators are supported too (e.g. `#id=c9b07510d5`, `#id=abc123,def456`, `#id*=c9b0`, `#id^=c9`, `#id$=510d5`), including aliases `#video...`, `#videoid...`, and `#vid...`
- unknown `#tag` tokens are rendered as warning chips with an inline `unknown tag:*` message
- unknown non-duration tags include `did you mean` replacement buttons for typo repair (e.g. `#cachedd` -> `#cached`)
- comparator-family typos are suggested too (e.g. `#dru>5` -> `#dur>5`, `-#srd>3k` -> `-#src>3k`, `#filname=clip.mp4` -> `#filename=clip.mp4`, `#reslution=320x240` -> `#resolution=320x240`)
- malformed comparator example rows are hidden whenever a direct `did you mean` replacement is available
- malformed `#out...` / `#outputs...` comparator tags show clickable output examples (`#out>=1`, `#out=0`) and preserve include/exclude prefix + alias choice
- malformed `#src...` / `#source...` / `#sourcebytes...` / `#mb...` / `#render...` / `#outputbytes...` comparator tags show clickable storage examples (`#src>3k`, `#mb>0b`, `#src>10m`) and preserve include/exclude prefix + alias choice
- malformed `#ext...` / `#format...` comparator tags show clickable extension examples (`#ext=mp4`, `#ext=mp4,mov`, `#ext!=mp4`) and preserve include/exclude prefix + long alias choice
- malformed `#name...` / `#file...` / `#filename...` comparator tags show clickable name examples (`#name=clip.mp4`, `#name=clip.mp4,other.mp4`, `#name!=clip.mp4`, `#name*=clip`) and preserve include/exclude prefix + alias choice
- malformed `#id...` / `#video...` / `#videoid...` / `#vid...` comparator tags show clickable id examples (`#id*=abc`, `#id^=c9b0`, `#id=deadbeef00`, `#id=abc123,def456`) and preserve include/exclude prefix + alias choice
- malformed `#fps...` / `#w...` / `#h...` / `#ar...` / `#fc...` / `#res...` comparator tags show clickable video-meta examples (`#fps>=24`, `#fps=24..60`, `#w>=1080`, `#h>=1080`, `#ar>=1.3`, `#fc>=25`, `#res=1920x1080`) and preserve long-form aliases (`#framerate...`, `#width...`, `#height...`, `#aspect...`, `#ratio...`, `#frames...`, `#resolution...`) when typed
- malformed range comparators show clickable range examples (`#dur=1..2`, `#dur=..2`, `#src=2k..4k`, `#src=2k..`, `#out=0..2`, `#ar=1.3..1.8`, `#fc=25..200`) and preserve long aliases like `#height=..x` -> `#height=..1920`
- malformed `#dur...` / `#time...` / `#duration...` comparator tags also show inline duration-format examples (`#dur>90s`, `#dur>1m30s`)
- duration-format example tags are clickable to replace malformed `#dur` tokens immediately
- malformed exclude tokens (`-#dur...` / `!#dur...`) keep their typed exclude prefix when applying a duration example button
- active filter chips are shown for parsed terms (`+term` includes, `-term` / `!term` excludes)
- clicking a filter chip removes that term from the query immediately
- partial tag input (like `#c` / `-#o`) shows suggestions, and `Tab` autocompletes the first suggestion
- comparator fragments like `#src=` / `#mb=` / `#out=` / `#dur=` / `#fps=` / `#w=` / `#h=` / `#ar=` / `#fc=` / `#res=` / `#ext=` / `#name=` / `#id=` (plus long forms `#source=` / `#sourcebytes=` / `#render=` / `#outputbytes=` / `#outputs=` / `#time=` / `#duration=` / `#framerate=` / `#width=` / `#height=` / `#aspect=` / `#ratio=` / `#frames=` / `#resolution=` / `#format=` / `#file=` / `#filename=` / `#video=` / `#videoid=` / `#vid=`) keep root suggestions visible for fast correction (including range presets like `#src=2k..4k`, `#dur=1..2`, `#dur=..2`, `#fps=24..60`, `#ar=1.3..1.8`, `#fc=25..200`)
- duration suggestions include unit-aware templates (`#dur>90s`, `#dur>1m30s`)
- when tag suggestions are visible, `Enter` autocompletes first; a second `Enter` loads filtered clip, while `Shift+Enter` bypasses autocomplete to load immediately
- when tag suggestions are visible, `ArrowUp` / `ArrowDown` cycles suggestions before `Enter`/`Tab` apply
- focusing an empty filter input shows quick one-click tag buttons for simple tags plus comparator/range presets (e.g. `#cached`, `#landscape`, `#out>=1`, `#src=2k..`, `#dur=..2`)
- quick tag buttons show live match counts (`#tag:N`) but insert plain tag tokens when clicked
- zero-match quick tags are collapsed by default and can be expanded via `[+N zero]` (`[hide 0s]` when expanded)
- `/` keyboard shortcut focuses recent filter input when no clip is loaded
- `Alt+Backspace` (or `Ctrl/Cmd+Backspace`) in recent filter input removes the last query term quickly
- `Esc` clears active recent filter text and restores default preview
- pressing `Enter` in recent filter input loads the first matching clip immediately (`Shift+Enter` forces load even when tag suggestions are open)
- `ArrowUp` / `ArrowDown` in recent filter input moves a visible-clip cursor with wrap-around when no tag suggestion is open; `Enter` loads that highlighted clip
- `Home` / `End` in recent filter input jumps the cursor to the first/last visible clip
- `PageUp` / `PageDown` in recent filter input jumps the visible-clip cursor by 5 slots
- selected keyboard target is rendered with a `▶` prefix in the recent row
- recent row displays `1-0` slot markers for quick keyboard load targeting (`0` = slot 10)
- recent filter text is persisted across reloads with other recent-view preferences
- stale/missing source files are automatically dropped from Recent on refresh
- refresh action shows temporary loading label while list rescan is in progress
- recent header displays a live item count (`Recent (N)`)
- recent header also shows total local duration (`Recent (N · M:SS)`)
- when filter is active, header shows filtered vs total counts/durations (`n/N · m:ss/M:SS`)
- dropzone now shows inline feedback text for local library actions (rename/delete/clear results)
- recent row supports sort cycling between recency, filename, duration, output-count, and source-size ordering
- recent sort mode, reverse toggle state, and expanded/collapsed preview state are remembered across reloads

## Common scripts

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## Main folders

- `app/` — App Router entry (`layout.tsx`, `page.tsx`, global styles)
- `components/` — UI modules (timeline, settings, controls, upload/player)
- `lib/` — API client + Zustand store + shared UI types

## Current UX highlights

- Hybrid / progress / action mode controls
- Pin + keyframe timeline editing (keyboard nudging + delete shortcuts + bracket radius nudging + numeric pin/keyframe values)
- `from crux` quick-fill actions for both pins and keyframes
- timeline mode conversion actions (`from pins`, `from keyframes`) preserve edits across modes
- timeline ordering tools (`sort pins`, `sort keyframes`) for quick re-normalization
- Quick Preview and full Render actions
- Keyboard transport shortcuts (`Ctrl/Cmd+Shift+A` = Analyze/Cancel, `Ctrl/Cmd+Enter` = Quick Preview, `Ctrl/Cmd+Shift+Enter` = Full Render)
- Player shortcuts (`K`/`Space` = play-pause, `J`/`L` = seek -/+ 1 second, `,`/`.` = frame step)
- Output templates + chapter overlays
- Output aspect options (`original`, `9:16`, `1:1`) + auto-reframe
- Active render cancellation (`CANCEL (ESC)` button, Escape shortcut)
