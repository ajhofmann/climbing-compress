# AGENTS.md

SENDIT / `climb-ramp`: a climbing-video speed-ramper. Python FastAPI backend (`server.py` + `pipeline/`) does MediaPipe pose detection, movement/progress scoring, speed-curve solving, and FFmpeg rendering. The Next.js frontend in `app/` is a retro VCR-styled UI for upload → analyze → tweak curve → render.

## Cursor Cloud specific instructions

### Services
- **Backend** (FastAPI): `.venv/bin/python server.py` — serves on port `8000` (host `0.0.0.0`). Override with `PORT`/`HOST` env vars. Data is written under `data/` (gitignored).
- **Frontend** (Next.js dev): `cd app && npm run dev` — serves on port `3000`. It calls the backend at `http://localhost:8000` (override with `NEXT_PUBLIC_API_URL`). CORS on the backend defaults to `http://localhost:3000`.
- Both services must be running to test the product end to end.

### Python environment
- Backend deps live in a virtualenv at `.venv` (the update script creates it and installs `pip install -e ".[dev]"`). Always invoke backend tooling via `.venv/bin/...` (e.g. `.venv/bin/pytest`, `.venv/bin/python server.py`) or activate with `source .venv/bin/activate`.
- System libraries `libegl1 libgl1 libglib2.0-0 libgomp1` are required by MediaPipe/OpenCV (analyze fails with `libEGL.so.1: cannot open shared object file` without them), and `python3.12-venv` is required to create the venv. These are installed at the system level (persisted in the VM snapshot), not by the update script.
- `ffmpeg` must be on `PATH` (used for rendering); it is preinstalled.
- The optional `[tracking]` extra (YOLOv8 + ByteTrack) is NOT installed — it pulls large model weights. Analyze with `use_tracker: false` (pose + optical-flow path works without it).

### Lint / test / build (see also `CONTRIBUTING.md` and `.github/workflows/ci.yml`)
- Backend tests: `.venv/bin/pytest -q`. Note: `tests/test_server_endpoints.py::test_delete_outputs_for_video_removes_only_matching_stem` fails on a clean checkout — it is a pre-existing test/impl mismatch (`_resolve_output_owner_video_id` only resolves a bare-stem output when the id is registered in the in-memory `_videos`/render-history, which the test never sets up), unrelated to environment setup. The other 181 tests pass.
- Frontend: `cd app && npm run lint` (ESLint; currently emits only `no-unused-vars` warnings, 0 errors), `npx tsc --noEmit` (typecheck), `npm run build`.

### Testing notes
- No sample videos ship in the repo (`examples/` is empty). Tests generate a synthetic clip via `tests/conftest.py`. For manual end-to-end testing you can generate a synthetic humanoid clip with OpenCV; MediaPipe will detect poses on a simple stick-figure render.
- The analyze and render endpoints stream Server-Sent Events (SSE); a request that returns `{"error": true}` in a `data:` line indicates a pipeline error rather than an HTTP failure.
