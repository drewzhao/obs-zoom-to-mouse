# macOS Retina and Display-Coordinate Handling

This document explains the current macOS Retina / HiDPI coordinate handling in the maintained Lua implementation, `obs-zoom-to-mouse.lua`.

It is written as a current reference, not as a historical bug report. The old Retina centering bug is still described near the end because it explains why the current detection pipeline exists.

## Current Status

The Lua script is the only maintained runtime.

On macOS, the script supports:

- automatic display-capture geometry detection;
- per-display `display_uuid` lookup;
- `NSScreen` frame and backing-scale detection;
- fallback display-name parsing;
- user-selectable Retina interpretation modes;
- manual source-position override for edge cases.

The current implementation is designed to handle mixed Retina and non-Retina monitor layouts without assuming that the main screen is the captured screen.

## Why This Is Needed

macOS and OBS expose display information through different coordinate systems.

| Data | Typical Unit | Typical Origin | Used For |
|------|--------------|----------------|----------|
| `NSEvent.mouseLocation` | logical points | bottom-left global screen space | local cursor position |
| `NSScreen.frame` | logical points | bottom-left global screen space | display position and logical size |
| OBS display-capture source size | pixels | top-left source space | Crop/Pad and zoom math |
| OBS display list label | usually logical points, but classified defensively | label text only | fallback geometry parsing |

The script must turn a macOS point-space mouse coordinate into a source pixel coordinate before it can calculate the Crop/Pad rectangle used for zooming.

## Current Detection Pipeline

The central function is `get_monitor_info(source, source_pixels)`.

For display-capture sources on macOS, the script follows this order:

1. Read the selected OBS display-capture property.
   - Modern macOS capture sources use `display_uuid`.
   - The display list item label is also read so it can be parsed if needed.
2. Try native display lookup.
   - Convert `display_uuid` to `CGDirectDisplayID`.
   - Match that display ID to an `NSScreen`.
   - Read that screen's `frame` and `backingScaleFactor`.
3. In `Auto` mode, use native geometry immediately when available.
   - This is the preferred path because it identifies the captured screen directly.
4. If native geometry is unavailable, or if the user selected a force mode, parse the OBS display list label.
   - The parser extracts `width`, `height`, `x`, and `y` from labels shaped like `Display Name: 2560x1440 @ 0,0`.
   - The parsed dimensions are then interpreted by `derive_macos_display_metrics(...)`.
5. If parsing fails but native geometry exists, fall back to native geometry as a last resort.
6. If automatic detection cannot produce usable geometry, the script asks the user to enable `Set manual source position`.

ASCII flow:

```text
OBS source settings
        |
        v
selected display_uuid
        |
        +--> CGDisplayGetDisplayIDFromUUID
                 |
                 v
             matching NSScreen
                 |
                 v
             frame + backingScaleFactor

OBS display list label
        |
        v
parse "WxH @ x,y"
        |
        v
classify as points or pixels when native geometry is unavailable or force mode is selected
```

## Retina Detection Modes

`Retina detection mode` appears in the OBS Scripts UI on macOS.

| Mode | Behavior | When to Use |
|------|----------|-------------|
| `Auto (recommended)` | Prefer native `display_uuid` -> `NSScreen` geometry. If that is unavailable, classify the parsed display label using source-size ratios and backing scale. | Normal use. Start here. |
| `Force display name as points` | Parse the OBS display list label and treat its `WxH` dimensions as logical points. | Use when auto fallback misclassifies a label that you know is in point space. |
| `Force display name as pixels` | Parse the OBS display list label and treat its `WxH` dimensions as physical pixels, deriving logical display height/width by dividing by backing scale. | Use when auto fallback misclassifies a label that you know is in pixel space. |

Force modes are only meaningful when the script can parse the OBS display label. If parsing fails, the script may still use native geometry as a last resort.

## Parsed-Name Classification

When the script has to classify parsed label dimensions, it compares the OBS source size against the parsed display-list size.

| Case | Example | Script Interpretation |
|------|---------|----------------------|
| Source-to-label ratio is close to the backing scale | source `5120x2880`, parsed `2560x1440`, scale `2.0` | Parsed label is point-sized. |
| Source-to-label ratio is close to `1` | source `3840x2160`, parsed `3840x2160`, scale `2.0` | Parsed label is pixel-sized. |
| Ratio is between `1` and `3` but does not match exactly | unusual scaled display mode | Derive a rounded scale from the ratios. |
| Source dimensions unavailable | source width/height are `0` or missing | Fall back to point-space interpretation. |

The current code uses a tolerance when comparing ratios so small OBS/macOS rounding differences do not break detection.

## Current Coordinate Pipeline

After `monitor_info` is available, `get_mouse_source_point(zoom)` maps the mouse into source space.

The current Lua order is:

```text
1. Read mouse position from NSEvent.mouseLocation.
   - Units: logical points.
   - Origin: bottom-left global macOS screen space.

2. Convert to local display point coordinates.
   local_x = mouse.x - monitor_info.x
   local_y = mouse.y - monitor_info.y

3. Flip Y into top-left display-local space.
   display_height = monitor_info.display_height or monitor_info.height
   mouse.y = display_height - local_y

4. Subtract source Crop/Pad offsets already applied before zoom.
   mouse.x = mouse.x - zoom.source_crop_filter.x
   mouse.y = mouse.y - zoom.source_crop_filter.y

5. Convert point-space movement to source pixels.
   mouse.x = mouse.x * monitor_info.scale_x
   mouse.y = mouse.y * monitor_info.scale_y

6. Use the resulting source-space point for zoom target calculation.
```

This order matters. The Y flip happens after subtracting the display's macOS global `y` offset, and Crop/Pad offsets are subtracted before the final scale is applied.

## Manual Source Position on macOS

Manual source position bypasses automatic display detection.

Use it when:

- the selected source is not a display-capture source;
- the display list cannot be parsed;
- native lookup fails and auto detection is visibly offset;
- you are zooming a cloned, cropped, or scaled source.

For macOS manual override, the fields should describe the desktop/display area represented by the source in the same logical coordinate space as macOS mouse coordinates before scaling. `Monitor Height` is especially important because the script uses it to flip Y from macOS bottom-left space into top-left source space.

Practical guidance:

- Prefer automatic detection for real display-capture sources.
- Start with `Retina detection mode = Auto`.
- Use debug logging before manual override.
- If the target is vertically inverted or offset on a secondary display, check `Y`, `Monitor Height`, and `Scale Y`.
- If the target is consistently too far from the cursor by a Retina factor, check `Scale X` and `Scale Y`.

## Debug Logging

Enable `Enable debug logging` in the OBS Scripts UI when diagnosing Retina behavior.

Useful log examples:

```text
[Retina] Selected display_uuid: 37D8832A-2D66-02CA-B9F7-8F30A301B230
[Retina] Resolved display_uuid to display_id: 1
[Retina] Native display geometry: uuid=37D8832A-2D66-02CA-B9F7-8F30A301B230, display_id=1, frame=2560x1440 @ 0,0, scale=2.000
[Retina] Final monitor_info source: native_uuid
```

```text
[Retina] Native display lookup failed: display_uuid did not resolve to a display
[Retina] Retina: mode=auto, parsed=2560x1440, source=5120x2880, backing_scale=2.000
[Retina] Auto: display name matches point space (ratio ≈ backing scale) (points, scale=2.000)
```

```text
[Retina] Retina: mode=auto, parsed=3840x2160, source=3840x2160, backing_scale=2.000
[Retina] Auto: display name already reports pixel dimensions (pixels, scale=2.000)
```

```text
[Retina] Retina: mode=force_pixels, parsed=2940x1912, source=5880x3824, backing_scale=2.000
[Retina] Retina mode forced to pixels (pixels, scale=2.000)
```

The most important line is `Final monitor_info source`:

| Source | Meaning |
|--------|---------|
| `native_uuid` | The script used `display_uuid` -> `NSScreen` geometry. This is the preferred auto path. |
| `parsed_name` | The script parsed the OBS display label and classified its dimensions. |
| `manual_override` | `Set manual source position` is enabled and automatic detection is bypassed. |

## Troubleshooting

### Zoom lands at the wrong vertical position

Likely causes:

- the display height is in the wrong coordinate space;
- the selected display is not the display that OBS is capturing;
- manual override `Monitor Height` is wrong;
- manual override `Y` does not match macOS global point coordinates.

Start by enabling debug logging and checking `Final monitor_info source`, `display_height`, and `scale_y`.

### Zoom is offset by roughly 2x

Likely causes:

- parsed point dimensions were treated as pixels;
- parsed pixel dimensions were treated as points;
- manual override scale is wrong.

Try `Auto` first, then test `Force display name as points` or `Force display name as pixels` if auto fallback is not choosing the right model.

### Mixed-DPI monitors behave differently

This is exactly why native display lookup exists. In `Auto` mode, the script tries to read the backing scale from the captured `NSScreen`, not from `[NSScreen mainScreen]`.

If native lookup fails, parsed-name fallback may use the main-screen backing scale. In that case, a force mode or manual override may be needed.

### Non-display sources are offset

Automatic Retina detection is built for display-capture sources. For arbitrary window, browser, scene, or cloned sources, enable `Set manual source position` and provide the represented source geometry explicitly.

## OBS Source Context

The script's behavior is shaped by OBS macOS capture internals:

- `plugins/mac-capture/mac-sck-common.m` builds macOS ScreenCaptureKit display list labels from `NSScreen.frame`, which is point-space geometry.
- `plugins/mac-capture/mac-sck-video-capture.m` configures display stream width and height from `CGDisplayModeGetPixelWidth/Height`, which are pixel dimensions for the captured display mode.
- Older `mac-display-capture.m` code paths also expose display UUIDs and display labels, but source dimensions and crop behavior can differ by capture path and OBS/macOS version.

The Lua script therefore uses both selected-display identity and source-size comparison instead of trusting a single displayed label.

## Legacy Bug This Replaced

Older versions mixed display point dimensions and source pixel dimensions incorrectly.

The critical bug was using a scaled-down height for the Y flip:

```lua
-- Wrong legacy behavior
info.display_height = info.height / backing_scale
mouse.y = display_height - point.y
```

On a 5K Retina display where the logical size is `2560x1440` and the source is `5120x2880`, this could produce a `display_height` such as `720` instead of `1440`. The result was a vertical error that became more visible toward the lower half of the screen.

The current script avoids this by keeping a logical `display_height` for the Y flip and applying the point-to-pixel scale later in the pipeline.

## Version Notes

| Area | Current Status |
|------|----------------|
| Lua implementation | Maintained. Uses native UUID lookup, parsed-name fallback, Retina detection modes, and manual override. |
| Python implementation | Removed. It used the same OBS Crop/Pad rendering path while adding a second runtime and dependency stack. |
| Automated tests | The current Lua smoke and contract tests do not emulate real macOS Retina hardware. Live OBS verification with debug logging is still the best end-to-end check for display-coordinate issues. |

## Verification Checklist

On a Mac, verify with a real OBS display-capture source:

1. Set `Retina detection mode` to `Auto`.
2. Enable debug logging.
3. Reload the script or refresh the zoom source.
4. Confirm the log shows either `native_uuid` or a sensible parsed-name classification.
5. Move the cursor to the center of the captured display and toggle zoom.
6. Repeat near each corner of the captured display.
7. Test a secondary monitor if the machine uses mixed-DPI displays.
8. Disable debug logging after diagnosis.

Expected result: the zoom target should align with the cursor in source space, and the frame should remain stable after zoom-in.
