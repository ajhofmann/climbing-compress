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
- Pin + keyframe timeline editing (with keyboard nudging + delete shortcuts)
- Quick Preview and full Render actions
- Keyboard transport shortcuts (`Ctrl/Cmd+Enter` = Quick Preview, `Ctrl/Cmd+Shift+Enter` = Full Render)
- Player shortcuts (`K`/`Space` = play-pause, `J`/`L` = seek -/+ 1 second)
- Output templates + chapter overlays
- Output aspect options (`original`, `9:16`, `1:1`) + auto-reframe
- Active render cancellation (`CANCEL (ESC)` button, Escape shortcut)
