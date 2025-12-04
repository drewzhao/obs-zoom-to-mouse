# macOS Retina Display Fix (v1.2.0)

## Bug Description

**Issue:** Zoom was not centering on the mouse correctly on macOS Retina displays. The offset error was more prominent when the cursor was in the lower half of the screen.

**Affected Versions:** v1.1.1 and earlier

**Platform:** macOS with Retina displays (2x or higher backing scale factor)

---

## Root Cause Analysis

### The Coordinate Space Mismatch

On macOS, there are two different coordinate spaces at play:

| Coordinate Space | Unit | Example (5K Retina) | Used By |
|------------------|------|---------------------|---------|
| **Points** (logical) | pt | 2560×1440 | `NSEvent.mouseLocation`, display names in OBS |
| **Pixels** (physical) | px | 5120×2880 | OBS source capture, crop filter |

The bug occurred because the script was mixing these coordinate spaces incorrectly.

### How macOS Reports Display Information

1. **OBS Display Name:** Reports dimensions in **points** (e.g., `"Studio Display: 2560x1440 @ 0,0"`)
   - This comes from `NSScreen.frame.size` which is in the point coordinate system

2. **OBS Source Dimensions:** Reports in **pixels** (e.g., `5120x2880`)
   - This comes from `CGDisplayModeGetPixelWidth/Height` or the actual captured frame

3. **Mouse Position (`NSEvent.mouseLocation`):** Returns coordinates in **points**
   - Origin is at the **bottom-left** of the primary display
   - Y-axis increases **upward** (opposite of most graphics systems)

### The Specific Bug

The script's Y-coordinate transformation was using the wrong height value:

```lua
-- Y-flip to convert from bottom-left origin to top-left origin
mouse.y = display_height - point.y
```

In v1.1.1, the code incorrectly set:
```lua
info.display_height = info.height / backing_scale  -- WRONG!
-- e.g., 1440 / 2 = 720
```

This caused:
- `display_height = 720` (incorrect, should be 1440)
- Mouse at top (point.y = 1440): `720 - 1440 = -720` → clamped/wrong
- Mouse at bottom (point.y = 0): `720 - 0 = 720` → wrong (should be 1440)

The error increased linearly from top to bottom of the screen.

---

## The Fix

### Key Insight

On macOS, the numbers shown in an OBS display name (e.g. `“Studio Display: 2560x1440 @ 0,0”`) may be reported in **points** *or* in **pixels** depending on the monitor, macOS scaling mode, and which capture backend is being used. The script therefore has to *classify* the coordinate space before it can convert mouse points into captured pixels.

### Detection Pipeline (v1.3.0+)

1. **Collect observations**
   - `parsed_width/height` – from the OBS display name.
   - `source_width/height` – actual pixels reported by the display-capture source.
   - `backing_scale` – `NSScreen.backingScaleFactor`.
2. **Auto classification**
   - If `source / parsed ≈ backing_scale`: the name is in **points** (logical coordinates).
   - If `source / parsed ≈ 1`: the name is already in **pixels**; divide by the backing scale to recover logical coordinates.
   - Otherwise, derive a reasonable scale from the ratios (rounded to the nearest 0.5) or fall back to assuming points when data is missing.
3. **User override (new)**
   - A *Retina detection mode* dropdown lets users force either interpretation when auto mode can’t deduce it.
4. **Manual override**
   - “Set manual source position” still bypasses auto detection entirely for edge cases.

### New Retina Detection Modes

| Mode | Description | Typical Use Case |
|------|-------------|------------------|
| `Auto (recommended)` | Uses the pipeline above to classify displays dynamically. | Works for most setups, including the “Retina 2560×1440” vs. “4K UI looks like 1920×1080” scenarios. |
| `Force display name as points` | Treats `WxH` from the display name as logical points. | Matches the v1.2.x behavior; useful if OBS always reports point dimensions on a particular Mac. |
| `Force display name as pixels` | Treats `WxH` as physical pixels and divides by the backing scale to get point coordinates. | Needed on some external 4K panels where OBS lists the native resolution even though the UI is scaled. |

### Logging Improvements

With “Enable debug logging” turned on, you now get detailed breadcrumbs in the script log:

```
[Retina] Retina: mode=auto, parsed=2560x1440, source=5120x2880, backing_scale=2.000
[Retina] Auto: display name matches point space (ratio ≈ backing scale) (points, scale=2.000)
```

```
[Retina] Retina: mode=auto, parsed=3840x2160, source=3840x2160, backing_scale=2.000
[Retina] Auto: display name already reports pixel dimensions (pixels, scale=2.000)
```

```
[Retina] Retina: mode=force_pixels, parsed=2940x1912, source=5880x3824, backing_scale=2.000
[Retina] Retina mode forced to pixels (pixels, scale=2.000)
```

These logs make it easy to verify which model the script chose on each Mac.

### Direct Backing Scale Factor Detection

The script still queries `[NSScreen mainScreen] backingScaleFactor` directly (with the `objc_msgSend_fpret`/`objc_msgSend` split between Intel and Apple Silicon) so that it never has to guess the scale purely from ratios.

---

## Coordinate Transformation Pipeline (Reference)

Once the display’s logical size is known, mouse coordinates flow through the system as follows:

```
1. NSEvent.mouseLocation -- returns (x, y) in POINTS, bottom-left origin
2. Y-flip: mouse.y = display_height - point.y  -- converts to top-left origin
3. Subtract monitor offsets (multi-monitor layouts)
4. Apply scale factor: mouse.x *= scale_x, mouse.y *= scale_y  -- convert to pixels
5. Use the pixel-space coordinates for crop calculations
```

---

## Workaround (For Older Versions)

If you cannot update to v1.2.0, you can use **"Set manual source position"**:

1. Enable "Set manual source position" checkbox
2. Set **Width** and **Height** to your display's **point** dimensions (e.g., 2560×1440)
3. Set **Monitor Width** and **Monitor Height** to the same values
4. Set **Scale X** and **Scale Y** to your backing scale factor (usually 2.0 for Retina)

This manually provides the correct values that the automatic detection was getting wrong.

---

## Testing

To verify the fix works correctly:

1. Move cursor to the **center** of screen → Zoom should center on cursor
2. Move cursor to **top-left** corner → Zoom should show top-left
3. Move cursor to **bottom-right** corner → Zoom should show bottom-right
4. Enable "Follow mouse" and move cursor around → Zoom should smoothly follow

The zoom center should match the cursor position regardless of where on the screen you click.

---

## Technical References

### OBS Source Code (macOS Display Capture)

- `plugins/mac-capture/mac-sck-common.m`: Display name generation using `NSScreen.frame.size` (points)
- `plugins/mac-capture/mac-sck-video-capture.m`: Source dimensions using `CGDisplayModeGetPixelWidth/Height` (pixels)

### Apple Documentation

- [NSScreen.backingScaleFactor](https://developer.apple.com/documentation/appkit/nsscreen/1388385-backingscalefactor)
- [NSEvent.mouseLocation](https://developer.apple.com/documentation/appkit/nsevent/1533416-mouselocation)
- [High Resolution Guidelines](https://developer.apple.com/library/archive/documentation/GraphicsAnimation/Conceptual/HighResolutionOSX/Explained/Explained.html)

---

## Version History

### Lua Version

| Version | Status | Notes |
|---------|--------|-------|
| v1.0.x | Buggy | No Retina support |
| v1.1.0 | Buggy | Added Retina detection (fallback method only) |
| v1.1.1 | Buggy | Attempted fix with incorrect display_height calculation |
| v1.2.0 | **Fixed** | Direct backing scale detection + correct coordinate handling |

### Python Version

| Version | Status | Notes |
|---------|--------|-------|
| v2.0.0 | Partial | Retina works (pynput handles Y-flip), but multi-monitor Y coords wrong |
| v2.1.0 | **Fixed** | Fixed multi-monitor Y coordinate system + direct backing scale detection |

---

## Python Version Fixes (v2.1.0)

The Python version had a different issue related to macOS coordinate systems:

### The Problem

On macOS, different APIs use different coordinate origins:

| API | Y Origin | Y Direction |
|-----|----------|-------------|
| `NSScreen.frame.origin` | Bottom of primary display | Upward |
| `pynput` / `CGEvent` | Top of primary display | Downward |

The `DisplayManager` was storing display Y positions from `NSScreen.frame.origin.y` without converting to the coordinate system used by `pynput`. This caused incorrect display offset calculations in multi-monitor setups.

### The Fix

In `display_manager.py`, the Y coordinate is now converted from macOS bottom-left origin to standard top-left origin:

```python
# Convert Y coordinate from macOS bottom-left origin to top-left origin
# In macOS: Y=0 is at bottom of primary display, Y increases upward
# In pynput/standard: Y=0 is at top of primary display, Y increases downward
standard_y = int(primary_height - (macos_y + screen_height))
```

Additionally, direct backing scale detection was added as the primary method:

```python
# Method 1: Direct backing scale detection on macOS
if sys.platform == 'darwin':
    backing_scale = get_macos_backing_scale_factor()
    if backing_scale > 1.0:
        scale_x = backing_scale
        scale_y = backing_scale
```

---

## Contributors

- Original bug report and testing: User community
- Lua fix implementation: v1.2.0
- Python fix implementation: v2.1.0

