# Examples

Before/after renders from outdoor climbing sessions. Each subfolder contains the source clip, rendered output, and a screenshot of the speed curve used.

## Adding your own

1. Create a folder named after the climb (e.g. `red-river-gorge-v4/`)
2. Drop in:
   - `raw.mp4` -- the original clip straight from your camera
   - `ramped.mp4` -- the speed-ramped render from SENDIT
   - `curve.png` -- screenshot of the timeline editor showing the speed curve
   - `thumb.jpg` -- a still frame for the gallery (optional)
3. Add a row to the table in the root [README.md](../README.md)

## Structure

```
examples/
├── README.md                  ← you are here
├── your-climb-name/
│   ├── raw.mp4                ← original footage
│   ├── ramped.mp4             ← SENDIT output
│   ├── curve.png              ← speed curve screenshot
│   └── notes.md               ← beta, grade, settings used (optional)
└── another-climb/
    └── ...
```

## Tips for good examples

- **Outdoor footage works best** -- varied backgrounds make the speed changes more visible
- **Include chalk-ups and rests** -- that's where the speed ramp really shines (boring parts get compressed)
- **Try different modes** on the same clip -- Constant Progress vs Action Highlight produce very different edits
- **Vertical video** works great for social -- use the 9:16 aspect preset in the Output panel
- Keep raw clips under 100MB for the repo, or use [Git LFS](https://git-lfs.github.com/) for larger files

## Generating social-ready clips

For a tweet or Instagram reel:

1. Load your clip in SENDIT
2. In the **Output** panel, set aspect to `9:16` and enable **auto-reframe**
3. Pick the **Social Vertical** style preset
4. **● RENDER** and grab the output from the renders folder
