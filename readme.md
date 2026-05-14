# OBS Zoom to Mouse

OBS Zoom to Mouse is a maintained Lua script for OBS Studio that zooms a selected source toward the mouse, a remote point, or a remote rectangle target.

It is tuned for software tutorials, code walkthroughs, product demos, and screen recordings where zoom should guide attention clearly without feeling flashy. The current implementation uses duration-based animation, easing presets, cursor-settle timing, safe-zone follow behavior, optional subtle overshoot, and macOS Retina-aware coordinate handling.

The Lua script is now the only maintained runtime. The earlier Python implementation has been removed because it used the same OBS Crop/Pad rendering path while adding a second dependency stack.

Inspired by [tryptech](https://github.com/tryptech)'s [obs-zoom-and-follow](https://github.com/tryptech/obs-zoom-and-follow).

## Relationship to Upstream

This project began as a fork of `BlankSourceCode/obs-zoom-to-mouse`.

It was detached from GitHub's fork network on 2026-05-14 so it can be maintained as an independent project with a different roadmap. Detaching the repository does not remove attribution, rewrite Git history, change the license status of the original work, or imply that this project is the original upstream project.

- Original upstream project: [BlankSourceCode/obs-zoom-to-mouse](https://github.com/BlankSourceCode/obs-zoom-to-mouse)
- Fork point / base commit: `53dc1a5425c2a96db34fb34aae40283f84bf1720`
- Base commit date: 2024-02-12
- Original license status: no `LICENSE` file is present in this repository snapshot. This README does not grant additional rights or relicense upstream work.
- Original copyright notice: `obs-zoom-to-mouse.lua` retains `Copyright (c) BlankSourceCode.  All rights reserved.`
- Git history is preserved so upstream contributors remain credited in commit metadata.

This repository is not endorsed by, affiliated with, or presented as an official continuation of the upstream project unless the upstream project says so explicitly. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for provenance details.

## Example

![Usage Demo](obs-zoom-to-mouse.gif)

## Documentation

Read the docs for usage details:

- [User guide](docs/USER_GUIDE.md): installation, recommended setup, hotkeys, presets, tuning, remote targeting, troubleshooting, and verification.
- [Lua design and architecture](docs/LUA_SCRIPT_DESIGN_AND_ARCHITECTURE.md): how the script is structured internally, including OBS lifecycle, Crop/Pad ownership, target framing, animation, follow behavior, and cleanup.
- [Retina display notes](docs/RETINA_DISPLAY_FIX.md): macOS coordinate-space behavior and debugging guidance.
- [Attributions](ATTRIBUTIONS.md): upstream provenance, fork point, and copyright notice details.

The README is intentionally a quick entrypoint. Treat the user guide as the source of truth for operating the script.

## Requirements

- OBS Studio with Lua scripting support.
- A display-capture source for automatic source geometry detection.
- Optional: `ljsocket.lua` next to `obs-zoom-to-mouse.lua` for UDP remote mouse and rectangle targeting.

The Lua script is intended for Windows, Linux, and macOS. macOS Retina and mixed-DPI behavior is documented separately in [docs/RETINA_DISPLAY_FIX.md](docs/RETINA_DISPLAY_FIX.md).

The script can also zoom non-display sources, but those usually require manual source-position settings because OBS does not expose enough desktop geometry for arbitrary sources.

## Quick Start

1. Clone this repo or save a copy of `obs-zoom-to-mouse.lua`.
2. Launch OBS.
3. Add a `Display Capture` source to the scene.
4. Open `Tools -> Scripts`.
5. Add `obs-zoom-to-mouse.lua`.
6. Select your display capture in `Zoom Source`.
7. Keep `Motion Preset` set to `Tutorial` for a natural default.
8. Open `Settings -> Hotkeys`.
9. Assign `Toggle zoom to mouse`.
10. Optionally assign `Toggle follow mouse during zoom`.

For exact source transform recommendations and all setting details, read [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Current Usage Model

The script behaves like a virtual camera over the selected OBS source:

```text
cursor or remote target
        |
        v
source-coordinate target
        |
        v
eased crop animation
        |
        v
OBS Crop/Pad filter update
```

When the zoom hotkey is pressed, the script optionally waits briefly for the cursor to settle, computes a target crop rectangle, and animates OBS's Crop/Pad filter toward that crop. Pressing the same hotkey again zooms back out.

While zoomed in, follow mode can keep the cursor in view. The follow system includes a safe zone so the frame can stay stable while you move the cursor around the focused content.

## Main Controls

The current script UI includes:

- `Motion Preset`: `Tutorial`, `Quick Focus`, `Detailed Inspection`, `Energetic Demo`, `Reduced Motion`, or `Custom`.
- `Zoom Factor`: how far to zoom in.
- `Zoom In Duration (ms)` and `Zoom Out Duration (ms)`: duration-based animation timing.
- `Zoom In Easing` and `Zoom Out Easing`: easing curves for the camera movement.
- `Cursor settle before zoom`: short pre-zoom delay that avoids starting a zoom during fast cursor movement.
- `Auto follow mouse`, `Follow Speed`, `Follow Border`, and `Lock Sensitivity`: safe-zone follow behavior while zoomed.
- `Zoom Overshoot`: optional subtle settle for energetic demos.
- `Scale Filter Policy`: optional helper for OBS scene-item scale filtering.
- `Retina detection mode`: macOS coordinate handling for mixed point/pixel display setups.
- `Allow any zoom source` and `Set manual source position`: advanced geometry controls for non-display or cloned sources.
- `Enable remote mouse listener`: optional UDP control when `ljsocket.lua` is available.

Do not tune from this list alone. The recommended ranges, defaults, and troubleshooting paths are in [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Remote Targeting

If `ljsocket.lua` is installed next to the Lua script, the remote listener supports:

```text
x y
```

and:

```text
rect x y width height
```

Rectangle targets let an external controller ask OBS to frame an entire button, menu item, code block, chart region, or UI panel instead of only centering on a point. See the [remote targeting section](docs/USER_GUIDE.md#remote-mouse-and-rectangle-targeting) for details.

## Development

Edit `obs-zoom-to-mouse.lua`, then click `Reload Scripts` in the OBS Scripts window.

Useful local checks:

```sh
python3 -m unittest discover -v
luajit tests/obs_lua_smoke.lua
luajit tests/obs_lua_target_rect.lua
luajit tests/obs_lua_scale_overshoot.lua
```

Python is used here only for repository tests. The maintained OBS runtime is Lua.

## Known Limits

- Display-capture sources are the best-supported automatic path.
- Non-display sources require manual geometry.
- OBS Crop/Pad uses integer crop values, so the script cannot promise true subpixel crop motion.
- The script sees captured pixels and cursor/remote coordinates; it does not semantically recognize UI controls by itself.
- Scale-filter changes are opt-in because OBS persists scene-item scale filters in scene data.

More detail lives in the [user guide](docs/USER_GUIDE.md) and [architecture guide](docs/LUA_SCRIPT_DESIGN_AND_ARCHITECTURE.md).

## Support

Want to support the original project author?

<a href="https://www.buymeacoffee.com/blanksourcecode" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>
