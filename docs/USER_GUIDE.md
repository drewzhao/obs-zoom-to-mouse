# OBS Zoom to Mouse User Guide

This guide explains how to install, configure, and operate the maintained Lua implementation of OBS Zoom to Mouse.

The current implementation is designed for software tutorials, code walkthroughs, demos, and screen recordings where zoom should guide attention without feeling flashy. It follows the principles documented in `LUA_SCRIPT_DESIGN_AND_ARCHITECTURE.md`: clear target, smooth easing, minimal translation, stable ending, and predictable defaults.

## What the Script Does

OBS Zoom to Mouse zooms a selected display-capture source toward the cursor or an external target. It does this by adding and updating an OBS `Crop/Pad` filter named `obs-zoom-to-mouse-crop` on the selected source.

When you press the zoom hotkey, the script:

1. Reads the current cursor or remote target.
2. Optionally waits briefly for the cursor to settle.
3. Calculates a source-coordinate crop rectangle.
4. Animates the crop with easing over a configured duration.
5. Holds the zoomed frame until you toggle zoom out.
6. Optionally follows the cursor while zoomed.

The script moves the captured source as one layer. It does not animate separate UI elements, add camera shake, or create fake lag between interface parts.

## Supported Implementation

The Lua script is the single maintained implementation:

- Main script: `obs-zoom-to-mouse.lua`
- Lua design and architecture: `LUA_SCRIPT_DESIGN_AND_ARCHITECTURE.md`
- Retina display notes: `RETINA_DISPLAY_FIX.md`

The previous Python edition has been removed because it used the same OBS Crop/Pad rendering path while adding a second runtime, dependency setup, and duplicate maintenance burden.

## Requirements

- OBS Studio with Lua scripting support.
- A display-capture source for automatic source-position detection.
- Optional: `ljsocket.lua` next to `obs-zoom-to-mouse.lua` if you want UDP remote mouse or rectangle targeting.

The script can also work with non-display sources, but only if you enable manual source positioning and provide correct source geometry.

## Recommended Quick Start

1. Add a `Display Capture` source to your OBS scene.
2. Open `Tools -> Scripts`.
3. Add `obs-zoom-to-mouse.lua`.
4. In the script settings, choose your display capture in `Zoom Source`.
5. Keep `Motion Preset` set to `Tutorial`.
6. Open `Settings -> Hotkeys`.
7. Assign a hotkey to `Toggle zoom to mouse`.
8. Optionally assign a hotkey to `Toggle follow mouse during zoom`.
9. Press the zoom hotkey with the cursor near the UI element you want to focus.

The default `Tutorial` preset is a good starting point for most recordings:

| Setting | Default |
|---------|---------|
| Zoom Factor | `1.45x` |
| Zoom In Duration | `420ms` |
| Zoom Out Duration | `320ms` |
| Zoom In Easing | `ease_out_cubic` |
| Zoom Out Easing | `ease_in_out_cubic` |
| Cursor settle before zoom | On |
| Cursor Stable Duration | `150ms` |
| Max Cursor Wait | `250ms` |
| Cursor Movement Threshold | `4px` |
| Zoom Overshoot | Off |
| Scale Filter Policy | Leave unchanged |

## Source Setup

For best results, configure the zoom source so the script can map cursor coordinates to source pixels accurately.

Recommended display-capture transform:

| OBS Transform Field | Recommended Value |
|---------------------|-------------------|
| Positional Alignment | Top Left |
| Bounding Box Type | Scale to inner bounds |
| Alignment in Bounding Box | Top Left |
| Transform Crop | All zeros |

If you need to crop the display capture, prefer an OBS `Crop/Pad` filter instead of transform crop:

| Crop/Pad Field | Recommended Value |
|----------------|-------------------|
| Relative | False |
| Left / X | Pixels cropped from left |
| Top / Y | Pixels cropped from top |
| Width | Final source width after crop |
| Height | Final source height after crop |

If the source transform is not compatible, the script may attempt to convert it into a zoom-compatible bounding-box and crop-filter setup. That can affect layout, so it is better to start from the recommended transform when possible.

## Hotkeys

### Toggle zoom to mouse

This is the main hotkey.

When not zoomed, it starts a zoom-in animation toward the current target. When already zoomed, it starts a zoom-out animation back to the original full-source crop.

### Toggle follow mouse during zoom

This optional hotkey toggles whether the zoomed crop follows cursor movement while zoomed. If `Auto follow mouse` is enabled, following starts automatically after zoom-in.

## Natural Motion Model

The script uses a virtual camera model built from crop rectangles:

```text
from crop -> eased animation -> to crop
```

The animation is duration-based, not frame-step based. Each timer tick advances by elapsed frame time, clamps progress to `0..1`, applies easing, and interpolates the crop.

This makes zoom timing more consistent across common frame rates and avoids the old behavior where animation speed depended on how often the timer fired.

## Target Framing

The script does not place the target exactly in the center by default. It uses a slight vertical bias:

| Axis | Target Screen Position |
|------|------------------------|
| X | `0.50` |
| Y | `0.45` |

That means the target settles horizontally centered and slightly above vertical center. This usually leaves more room below the target for cursor movement, captions, or explanatory context.

The bias is internal and not currently exposed as a UI setting.

## Motion Presets

Use `Motion Preset` to select a complete timing style. Choosing a preset updates the zoom factor, durations, easing, and overshoot settings. Choose `Custom` when you want to tune values manually.

| Preset | Zoom Factor | Zoom In | Zoom Out | Zoom In Easing | Zoom Out Easing | Overshoot | Best Use |
|--------|-------------|---------|----------|----------------|-----------------|-----------|----------|
| Tutorial | `1.45x` | `420ms` | `320ms` | `ease_out_cubic` | `ease_in_out_cubic` | Off | Default for screen recordings and tutorials. |
| Quick Focus | `1.35x` | `280ms` | `240ms` | `ease_out_cubic` | `ease_out_cubic` | Off | Quick emphasis without a large camera move. |
| Detailed Inspection | `1.75x` | `500ms` | `360ms` | `ease_in_out_cubic` | `ease_in_out_cubic` | Off | Code, text, charts, and close inspection. |
| Energetic Demo | `1.60x` | `350ms` | `260ms` | `ease_out_quart` | `ease_out_cubic` | Subtle `1.0%` | Shorter, more energetic demos. |
| Reduced Motion | `1.15x` | `100ms` | `100ms` | `ease_out_cubic` | `ease_out_cubic` | Off | Minimal movement while preserving focus. |
| Custom | User-defined | User-defined | User-defined | User-defined | User-defined | User-defined | Manual tuning. |

Recommended starting point: use `Tutorial`. Switch to `Detailed Inspection` only when the viewer needs to read small text. Use `Energetic Demo` sparingly and verify the result in a recorded clip.

## Easing Options

| Easing | Feel | Recommended Use |
|--------|------|-----------------|
| `ease_out_cubic` | Starts with intent, settles smoothly | Best general zoom-in default. |
| `ease_in_out_cubic` | Soft start and soft end | Tutorial-style zooms and zoom-out. |
| `ease_out_quart` | Snappier and more energetic | Marketing/demo zoom-in. |
| `ease_in_out_quart` | Slower, polished large movement | Large or deliberate moves. |
| `linear` | Mechanical | Debugging only. |

Avoid `linear` for normal recordings. Linear interpolation usually feels artificial.

## Zoom Controls

### Zoom Factor

Controls how far to zoom in. The UI allows `1.0x` to `5.0x`, but screen recordings should usually stay much lower.

Recommended ranges:

| Use Case | Range |
|----------|-------|
| Subtle focus | `1.10x-1.25x` |
| Normal UI focus | `1.25x-1.60x` |
| Detailed inspection | `1.60x-2.20x` |
| Code/text close-up | `1.40x-2.00x` |

Use the lowest zoom that makes the target readable. Very high zoom levels can make text soft after video compression.

### Zoom In Duration and Zoom Out Duration

The duration sliders control how long the camera transition takes. The UI allows `50ms` to `1200ms`.

Recommended ranges:

| Move Type | Range |
|-----------|-------|
| Quick focus zoom | `250ms-350ms` |
| Normal tutorial zoom | `350ms-500ms` |
| Large movement zoom | `500ms-700ms` |
| Reduced motion | Around `100ms` |

Very short durations can feel like jumps. Very long durations can distract from the content.

## Cursor Settle Before Zoom

`Cursor settle before zoom` is enabled by default. It coordinates the camera with cursor movement.

Default behavior:

1. You press the zoom hotkey.
2. The script waits for the cursor to stay within `4px` for `150ms`.
3. If the cursor keeps moving, the script waits up to `250ms`.
4. When either condition is met, zoom starts toward the latest target.

This makes the zoom feel intentional instead of random. Disable the group if you need immediate hotkey response.

Settings:

| Setting | Default | Meaning |
|---------|---------|---------|
| Cursor Stable Duration | `150ms` | How long the cursor must remain stable. |
| Max Cursor Wait | `250ms` | Maximum added delay before zoom starts anyway. |
| Cursor Movement Threshold | `4px` | Movement still considered stable. |

## Auto Follow and Safe Zone

When `Auto follow mouse` is enabled, following starts automatically after zoom-in. While following, the crop moves to keep the cursor visible.

The script also uses a safe-zone model:

1. After zoom-in, the camera can hold steady.
2. Moving the cursor near the crop edge re-enables following.
3. Once the camera catches up, it can lock again.

Follow settings:

| Setting | Default | Meaning |
|---------|---------|---------|
| Auto follow mouse | On | Start tracking automatically after zoom-in. |
| Follow outside bounds | Off | Track even when the cursor is outside the source bounds. |
| Follow Speed | `0.25` | How quickly the crop moves toward the cursor target. |
| Follow Border | `8` | Percent distance from edge that re-enables tracking. |
| Lock Sensitivity | `4` | How close the crop must get before locking again. |
| Auto Lock on reverse direction | Off | Stop tracking when cursor reverses toward center. |

If follow feels too busy, lower `Follow Speed`, increase `Follow Border` cautiously, or disable `Auto follow mouse` and use the follow hotkey manually.

## Zoom Overshoot

`Zoom Overshoot` adds a tiny two-part zoom-in settle:

1. Approach a crop that is slightly more zoomed in than the target.
2. Settle back to the final crop.

Defaults:

| Setting | Default |
|---------|---------|
| Zoom Overshoot | Off |
| Overshoot Amount | `1.0%` |
| Maximum UI Value | `2.0%` |

Only `Energetic Demo` enables subtle overshoot automatically. `Tutorial`, `Quick Focus`, `Detailed Inspection`, and `Reduced Motion` keep it off.

Use overshoot only when the recording style is intentionally energetic. For professional tutorials and code walkthroughs, leave it off unless a recorded clip proves it improves the result.

## Scale Filter Policy

`Scale Filter Policy` is an optional helper for OBS scene-item scale filtering.

| Policy | Behavior |
|--------|----------|
| Leave unchanged | Default. The script does not change the OBS scene-item scale filter. |
| Recommend in log | Writes a scale-filter recommendation to the OBS script log without changing the scene. |
| Temporarily set Lanczos | Temporarily sets the selected scene item to Lanczos while the script owns it, then restores the original value. |
| Temporarily set Bicubic | Temporarily sets the selected scene item to Bicubic while the script owns it, then restores the original value. |

Recommended guidance:

- Try `Lanczos` for sharper zoomed text.
- Try `Bicubic` if Lanczos looks too sharp or creates ringing.
- Avoid `Point` unless recording pixel art.
- Leave the policy unchanged if you already manage OBS scale filtering manually.

The helper is opt-in because OBS persists scene-item scale filters in scene data. Temporary policies preserve and restore the previous value when the script releases or changes the scene item.

## Retina Detection on macOS

On macOS, OBS display capture can involve logical points and physical pixels. The script includes Retina detection to map cursor positions to captured pixels.

`Retina detection mode` appears on macOS:

| Mode | Use |
|------|-----|
| Auto (recommended) | Use native display geometry or source/display ratios to infer the correct scale. |
| Force display name as points | Use when OBS display names are in logical point space. |
| Force display name as pixels | Use when OBS display names already report physical pixels. |

Keep `Auto` unless cursor targeting is visibly offset. If offset happens, enable debug logging and compare the logged monitor/source geometry against the actual display.

See `RETINA_DISPLAY_FIX.md` for the deeper coordinate-system explanation.

## Manual Source Position

Enable `Set manual source position` when:

- You selected a non-display source.
- The script cannot calculate source position automatically.
- Cursor targeting is offset and automatic detection is wrong.
- You are using a cloned or scaled source.

Manual fields:

| Field | Meaning |
|-------|---------|
| X | Left-most desktop pixel represented by the source. |
| Y | Top-most desktop pixel represented by the source. |
| Width | Width of the represented source area in pixels. |
| Height | Height of the represented source area in pixels. |
| Scale X | Scale factor between mouse coordinates and source pixels. Usually `1`. |
| Scale Y | Scale factor between mouse coordinates and source pixels. Usually `1`. |
| Monitor Width | Width of the monitor showing the source. |
| Monitor Height | Height of the monitor showing the source. |

For non-display sources, manual source position is required. OBS does not provide enough semantic information for the script to know where an arbitrary source sits on the desktop.

## Allow Any Zoom Source

By default, the source list shows display-capture sources because those are the sources the script can usually map automatically.

Enable `Allow any zoom source` only when you understand the geometry and are ready to provide manual source position values. Selecting arbitrary source types without manual geometry will usually produce wrong cursor targeting.

## Remote Mouse and Rectangle Targeting

If `ljsocket.lua` is available next to `obs-zoom-to-mouse.lua`, the script exposes `Enable remote mouse listener`.

Remote settings:

| Setting | Default | Meaning |
|---------|---------|---------|
| Enable remote mouse listener | Off | Start a UDP listener. |
| Port | `12345` | UDP port. |
| Poll Delay | `10ms` | How often OBS checks for UDP packets. |

The listener accepts two payload formats.

Point target:

```text
x y
```

Example:

```text
960 540
```

Rectangle target:

```text
rect x y width height
```

Example:

```text
rect 400 220 640 360
```

Rectangle coordinates are source coordinates. A rectangle target asks the camera to frame the whole region with margin instead of focusing on a single point. This is useful for remote/control integrations that know the bounds of a button, menu, code block, chart region, or UI panel.

The legacy point format remains supported.

## Debug Logging and More Info

Use `More Info` to print the script help text into the OBS script log.

Enable `Enable debug logging` when diagnosing:

- Cursor offset.
- Retina or monitor geometry.
- Remote listener behavior.
- Cursor-settle timing.
- Scale-filter policy behavior.
- Scene/source refresh behavior.

Disable debug logging after diagnosis so normal OBS use does not keep filling the script log.

## Recommended Recording Workflow

For tutorials:

1. Use `Tutorial`.
2. Keep overshoot off.
3. Keep cursor settle enabled.
4. Use zoom factors around `1.35x-1.60x`.
5. Let the zoomed frame hold while explaining the content.
6. Zoom out only after the viewer has had time to read.

For code or text close-ups:

1. Try `Detailed Inspection`.
2. Keep zoom below `2.0x` unless absolutely necessary.
3. Test the exported video, not only OBS preview.
4. Consider `Scale Filter Policy -> Recommend in log`, then manually try Lanczos or Bicubic if text is soft.

For energetic demos:

1. Try `Energetic Demo`.
2. Keep overshoot at `1.0%`.
3. Record a short sample.
4. If the settle is noticeable or distracting, turn overshoot off.

For reduced motion:

1. Use `Reduced Motion`.
2. Keep zoom factor low.
3. Consider using pauses and cursor placement instead of larger camera moves.

## Troubleshooting

### The Zoom Source list is empty

- Add a display-capture source to the current scene.
- Click `Refresh zoom sources`.
- Enable `Allow any zoom source` only if you intend to use manual geometry.

### The zoom targets the wrong position

- Confirm the selected `Zoom Source` is the source actually visible in the current scene.
- Check that the display source transform uses top-left alignment and no transform crop.
- On macOS, keep `Retina detection mode` on `Auto` first.
- Enable debug logging and check the logged monitor info.
- If automatic detection is wrong, enable `Set manual source position`.

### The zoom changes the source layout

The script may convert incompatible source transforms into a zoom-compatible setup. Restore the source manually if needed, then use the recommended transform setup before reloading the script.

### Text looks soft after zooming

- Lower `Zoom Factor`.
- Prefer `Tutorial` or `Detailed Inspection` rather than extreme custom zooms.
- Try OBS scene-item scale filtering manually.
- Use `Scale Filter Policy -> Recommend in log` for guidance.
- Test the exported recording after compression.

### The zoom feels abrupt

- Use `Tutorial` or `Quick Focus`.
- Avoid `linear` easing.
- Increase `Zoom In Duration` into the `350ms-500ms` range.
- Keep `Cursor settle before zoom` enabled.

### The zoom feels too slow

- Use `Quick Focus`.
- Lower `Zoom In Duration`.
- Avoid very large target moves and very high zoom factors.

### Remote messages do nothing

- Confirm `ljsocket.lua` is next to `obs-zoom-to-mouse.lua`.
- Enable `Enable remote mouse listener`.
- Confirm the UDP port matches `Port`.
- If changing port or poll delay, uncheck and re-check the remote listener group.
- Use debug logging to confirm the socket server starts.

## Developer Verification

After changing the Lua implementation or this guide, run:

```bash
python3 -m unittest discover -v
luajit tests/obs_lua_smoke.lua
luajit tests/obs_lua_target_rect.lua
luajit tests/obs_lua_scale_overshoot.lua
git diff --check
```

The LuaJIT tests exercise smoke loading, target rectangle math, scale-filter helper behavior, and overshoot math. The Python `unittest` suite currently verifies the Lua script contract from static and LuaJIT-backed tests.
