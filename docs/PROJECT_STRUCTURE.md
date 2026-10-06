# Project structure and cleanup rules

## Keep at repository root

Only the files required to understand or run the project:

- `README.md`
- `index.html`
- `render.py`

## Keep in `tools/`

Build/helper scripts only, especially `build_assets.py`.

## Keep in `assets/`

Only original source media required to reproduce the film. Generated derivatives belong in `assets/build/` and are ignored.

## Keep in `docs/`

Reference-only material such as the storyboard/keyframe sheet. Rename `sheet.jpg` to `storyboard-keyframes.jpg`.

## Keep in `output/`

One current delivery master:

- `lekker-ai-visualiser-final.mp4`

Do not keep multiple files named `final`, `final2`, `opus-final`, etc.

## Keep in `archive/`

Only meaningful historical milestones. The useful legacy file is:

- `lekker-ai-visualiser-v1-vector.mp4`

Source snapshots such as `index-opus-final.html` are unnecessary once Git history is in use.

## Expected source-asset count

16 visual source assets:

1. room-before
2. room-botanical
3. room-stripe
4. room-arch
5. room-grid
6. room-chalk
7. room-moss-trail
8. room-foreground
9. swatch-botanical
10. swatch-stripe
11. swatch-arch
12. swatch-grid
13. swatch-plain
14. swatch-moss-trail
15. wall-mask
16. wallpaper-flatlay

If any of these are absent after upload, the source pack is incomplete.
