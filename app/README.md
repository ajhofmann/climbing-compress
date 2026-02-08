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
- loaded clip toolbar displays active filename to clarify swap/delete actions
- loaded clip toolbar includes `[RENAME]` to relabel the active clip
- each recent pill has `✎` (rename) and `X` (delete) actions for local library cleanup
- rename actions preserve allowed video extensions and auto-append current extension when omitted
- rename actions are prevalidated client-side (length + extension) before API submission
- recent module shows explicit empty state (`no local clips`) and a `[refresh]` action to rescan local library
- stale/missing source files are automatically dropped from Recent on refresh

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
- Pin + keyframe timeline editing (with keyboard nudging + delete shortcuts + numeric pin/keyframe values)
- Quick Preview and full Render actions
- Keyboard transport shortcuts (`Ctrl/Cmd+Shift+A` = Analyze/Cancel, `Ctrl/Cmd+Enter` = Quick Preview, `Ctrl/Cmd+Shift+Enter` = Full Render)
- Player shortcuts (`K`/`Space` = play-pause, `J`/`L` = seek -/+ 1 second, `,`/`.` = frame step)
- Output templates + chapter overlays
- Output aspect options (`original`, `9:16`, `1:1`) + auto-reframe
- Active render cancellation (`CANCEL (ESC)` button, Escape shortcut)
