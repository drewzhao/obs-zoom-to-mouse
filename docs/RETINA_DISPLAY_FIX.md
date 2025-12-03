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

On macOS, the display name dimensions are **already in points**, not pixels. The scale factor should only be applied when converting mouse coordinates to source pixel coordinates, not when setting up the display dimensions for Y-flip.

### Code Changes

**Before (v1.1.1 - Buggy):**
```lua
if ffi.os == "OSX" then
    local backing_scale = get_osx_backing_scale_factor()
    if backing_scale > 1 then
        info.scale_x = backing_scale
        info.scale_y = backing_scale
        -- BUG: Dividing points by scale gives wrong result
        info.display_width = info.width / backing_scale
        info.display_height = info.height / backing_scale
    end
end
```

**After (v1.2.0 - Fixed):**
```lua
if ffi.os == "OSX" then
    local backing_scale = get_osx_backing_scale_factor()
    if backing_scale > 1 then
        info.scale_x = backing_scale
        info.scale_y = backing_scale
        -- CORRECT: Display dimensions stay in points (same as mouse coordinates)
        info.display_width = info.width
        info.display_height = info.height
    end
end
```

### Direct Backing Scale Factor Detection

v1.2.0 also adds direct detection of the backing scale factor via Objective-C runtime:

```lua
function get_osx_backing_scale_factor()
    -- Call [NSScreen mainScreen]
    local mainScreen = osx_msgSend(osx_nsscreen_class, osx_mainScreen_sel)
    
    -- Call [mainScreen backingScaleFactor]
    -- Returns 2.0 for Retina, 1.0 for non-Retina
    local scale = osx_msgSend_fpret(mainScreen, osx_backingScaleFactor_sel)  -- x64
    -- or
    local scale = ffi.cast("double(*)(void*, void*)", osx_msgSend)(...)      -- ARM64
    
    return scale
end
```

**Note:** `objc_msgSend_fpret` is only available on Intel (x64) Macs. On Apple Silicon (ARM64), the regular `objc_msgSend` is cast to return `double`.

---

## Coordinate Transformation Pipeline (Correct)

Here's how mouse coordinates should flow through the system:

```
1. NSEvent.mouseLocation
   └─→ Returns (x, y) in POINTS, bottom-left origin
       Example: (1280, 720) for center of 2560×1440 display

2. Y-flip (convert to top-left origin)
   └─→ mouse.y = display_height - point.y
       Example: 1440 - 720 = 720 (center, top-left origin)

3. Subtract monitor offset (for multi-monitor)
   └─→ mouse.x = mouse.x - monitor_info.x
       mouse.y = mouse.y - monitor_info.y

4. Apply scale factor (convert points to pixels)
   └─→ mouse.x = mouse.x * scale_x
       mouse.y = mouse.y * scale_y
       Example: (1280 * 2, 720 * 2) = (2560, 1440) in PIXELS

5. Use pixel coordinates for crop calculation
   └─→ Now matches the source's 5120×2880 pixel space
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

