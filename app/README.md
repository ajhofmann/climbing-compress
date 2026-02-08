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
- loaded clip toolbar includes `[PREV]` / `[NEXT]` to cycle through recent clips in-place (wrap-around)
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
- number keys `1-0` in dropzone load corresponding visible recent clip slots (`0` loads slot 10)
- `?` (Shift + `/`) or `[keys:on/off]` toggles inline dropzone shortcut help text
- `[keys:on/off]` help visibility state persists across reloads with Recent preferences
- keyboard shortcut `Ctrl/Cmd + Shift + O` clears outputs contextually (global in dropzone, clip-only in loaded toolbar)
- keyboard shortcut `Ctrl/Cmd + Alt + O` clears outputs for the active filtered subset in dropzone
- keyboard shortcuts `Alt+P` / `Alt+N` cycle previous/next recent clip while a clip is loaded
- keyboard shortcut `Alt+X` ejects the loaded clip back to the dropzone selector
- recent module supports overflow expansion (`[show all]` / `[show less]`) beyond six clip previews
- recent module supports inline name filtering with dedicated `no matching clips` empty state, space-separated AND-term matching, and `-term` exclusions
- active filter chips are shown for parsed terms (`+term` includes, `-term` excludes)
- clicking a filter chip removes that term from the query immediately
- `/` keyboard shortcut focuses recent filter input when no clip is loaded
- `Alt+Backspace` in recent filter input removes the last query term quickly
- `Esc` clears active recent filter text and restores default preview
- pressing `Enter` in recent filter input loads the first matching clip immediately
- `ArrowUp` / `ArrowDown` in recent filter input moves a visible-clip cursor with wrap-around; `Enter` loads that highlighted clip
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
