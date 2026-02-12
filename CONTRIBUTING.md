# Contributing

Thanks for helping improve `climb-ramp`.

## Development setup

```bash
# backend
pip install -e ".[dev]"

# frontend
cd app
npm install
```

## Run locally

```bash
# terminal 1
python server.py

# terminal 2
cd app
npm run dev
```

## Quality checks

```bash
# backend tests
pytest -q

# frontend checks
cd app
npm run lint
npx tsc --noEmit
```

## Pull request expectations

- Keep changes scoped and explain user impact.
- Add/update tests when behavior changes.
- Ensure lint and tests pass before opening a PR.
- Avoid committing local generated artifacts (`data/input`, `data/output`, `data/cache`, `data/eval`).
