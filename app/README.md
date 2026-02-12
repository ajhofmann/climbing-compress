# Frontend

Next.js app for climb-ramp: video upload, analysis controls, timeline editing, and render playback.

## Local development

```bash
npm install
npm run dev
```

App runs on [http://localhost:3000](http://localhost:3000). Backend defaults to `http://localhost:8000` (override with `NEXT_PUBLIC_API_URL`).

## Scripts

```bash
npm run lint      # eslint
npx tsc --noEmit  # typecheck
npm run build     # production build
```

## Structure

- `app/` -- App Router entry (`layout.tsx`, `page.tsx`, global styles)
- `components/` -- UI modules (timeline, settings, controls, upload/player)
- `lib/` -- API client, Zustand store, shared types
