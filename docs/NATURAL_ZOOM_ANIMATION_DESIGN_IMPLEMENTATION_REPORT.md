# Natural Zoom Animation Design and Implementation Report

## Purpose

This report evaluates the "Natural Screen-Recording Zoom Effects" guide against the current OBS Zoom to Mouse Lua implementation and defines a practical implementation plan for making zoom-in, zoom-out, and follow behavior feel more natural for software tutorials, demos, and code walkthroughs.

The goal is not to add flashy camera motion. The goal is to make the zoom behave like a calm visual guide:

- Clear target
- Smooth motion
- Minimal necessary translation
- Stable ending
- Predictable defaults

## Executive Summary

The guide makes good sense for this project. Most recommendations map directly to the current Lua architecture because the script already behaves like a virtual camera over a display capture source. It calculates a target crop rectangle from the mouse position and animates OBS Crop/Pad filter settings over time.

Approximately 80-85% of the guide can be implemented cleanly in Lua without changing OBS Studio. The remaining items require either semantic UI information, operating-system input hooks, or a custom OBS filter/plugin.
With the cursor-coordination milestone implemented, the current Lua path is at the upper end of that estimate for screen-recording zoom behavior.

Recommended first implementation:

1. Replace frame-step `zoom_speed` animation with elapsed-time `durationMs` animation.
2. Add easing presets with professional defaults.
3. Model animation as a camera transition from one crop state to another.
4. Add separate zoom-in and zoom-out duration/easing settings.
5. Add target framing bias so the mouse target can settle slightly above center.
6. Lower default zoom factor from `2.0x` to a more natural tutorial value such as `1.45x`.
7. Keep overshoot disabled by default.
8. Add reduced-motion and cursor-stability delay after the core animation model is stable.

## Implementation Status

Current implementation pass:

| Milestone | Status | Verification |
|-----------|--------|--------------|
| Design/report | Complete | Report is checked in under `docs/`. |
| Duration/easing camera animation | Complete | Static contract tests verify the old frame-step path is removed and the camera animation state is present. |
| Natural presets and target framing bias | Complete | Static contract tests verify preset settings, duration/easing controls, and biased target framing. |
| OBS load and live toggle smoke | Complete | OBS 32.0.4 loaded the script, rendered the new controls, and toggled zoom in/out through the saved `Ctrl+1` hotkey. |
| Legacy profile preset migration | Complete | Existing profiles with old `zoom_value` or `zoom_speed` settings are marked `Custom` unless a motion preset was explicitly saved. |
| Tutorial preset motion validation | Complete | OBS live validation used the `Tutorial` preset at `1.45x`, `420ms` zoom-in, and `320ms` zoom-out for repeated hotkey cycles. |
| Cursor coordination delay | Complete | Static contract tests verify the settings and pending wait state; live OBS validation confirmed the `150ms` cursor-stability wait before zoom-in. |
| Overshoot/advanced polish | Deferred | This remains optional and should stay disabled by default. |

Verification commands used for the current pass:

```bash
luajit tests/obs_lua_smoke.lua
python3 -m unittest discover -v
PYTHONPYCACHEPREFIX=/private/tmp/obs-zoom-to-mouse-pycache python3 -m py_compile tests/test_lua_natural_zoom_animation.py
python3 -B -m unittest tests.test_lua_natural_zoom_animation -v
git diff --check
```

Live OBS verification on this machine:

- OBS 32.0.4 loaded `obs-zoom-to-mouse.lua` with no script-log errors.
- The Scripts dialog rendered the new `Motion Preset`, `Zoom In Duration (ms)`, `Zoom Out Duration (ms)`, `Zoom In Easing`, and `Zoom Out Easing` controls.
- The current profile already had `toggle_zoom_hotkey` bound to `Ctrl+1`.
- Pressing `Ctrl+1` zoomed the `macOS Screen Capture` source in, and pressing it again restored the normal framing.
- The active OBS log recorded `Loaded lua script: obs-zoom-to-mouse.lua` and the expected `obs-zoom-to-mouse-crop` filter on the source.

Tutorial preset motion validation:

- The live OBS profile was switched from legacy/custom settings to `Motion Preset = Tutorial`.
- OBS showed the expected preset values: `Zoom Factor = 1.45`, `Zoom In Duration = 420ms`, `Zoom Out Duration = 320ms`, `Zoom In Easing = ease_out_cubic`, and `Zoom Out Easing = ease_in_out_cubic`.
- With debug logging temporarily enabled, repeated `Ctrl+1` cycles logged `Zooming in`, `Zoomed in`, `Tracking mouse is on`, `Zooming out`, and `Zoomed out`.
- The preview returned to normal framing after each cycle, and debug logging was disabled after validation so normal OBS use does not keep opening the script log.
- This was a live visual/runtime validation, not a frame-by-frame recorded motion analysis. A recorded 30 FPS/60 FPS comparison remains the next deeper quality gate if the tutorial preset needs fine tuning.

Cursor coordination implementation validation:

- `Cursor settle before zoom` is now a checkable OBS setting, enabled by default.
- The default settle behavior waits for `150ms` of stable cursor movement, with a `250ms` max wait and `4px` movement threshold.
- The zoom-in hotkey now enters a pending state before animation. The timer samples the latest cursor-derived target, starts zoom when the cursor is stable, or starts zoom at the latest cursor position when the max wait is reached.
- Debug logging records when the stability wait starts, when movement resets the wait, when the cursor is stable, and when the max wait cap starts the zoom.
- Automated validation has passed through `python3 -m unittest discover -v` and `luajit tests/obs_lua_smoke.lua`.
- Live OBS validation on this machine reloaded the script, rendered the new cursor-settle group, and showed `Cursor settle before zoom` enabled with `150ms` stable duration, `250ms` max wait, and `4px` threshold.
- With debug logging temporarily enabled, a `Ctrl+1` zoom-in cycle logged `Cursor stability wait started (stable=150ms, max=250ms, threshold=4px)`, then `Cursor stable for 166ms; starting zoom`, then `Zoomed in`.
- The matching `Ctrl+1` zoom-out cycle logged `Zooming out`, `Tracking mouse is off (due to zoom out)`, and `Zoomed out`; the preview returned to normal framing.
- Debug logging was disabled again after validation.

## Baseline Implementation Findings

### Current Motion Model

Before this implementation pass, the Lua script implemented zoom by changing the selected source's Crop/Pad filter:

- `get_target_position(zoom)` converts the mouse position into a target crop rectangle.
- `on_toggle_zoom(pressed)` sets the zoom state and target.
- `on_timer()` advances the animation.
- `set_crop_settings(crop)` writes `left`, `top`, `cx`, and `cy` into the OBS Crop/Pad filter.

The baseline zoom animation was controlled by:

```lua
zoom_time = zoom_time + zoom_speed
crop_filter_info.x = lerp(crop_filter_info.x, zoom_target.crop.x, ease_in_out(zoom_time))
crop_filter_info.y = lerp(crop_filter_info.y, zoom_target.crop.y, ease_in_out(zoom_time))
crop_filter_info.w = lerp(crop_filter_info.w, zoom_target.crop.w, ease_in_out(zoom_time))
crop_filter_info.h = lerp(crop_filter_info.h, zoom_target.crop.h, ease_in_out(zoom_time))
```

This is simple and already usable, but it has three important limitations:

1. `zoom_speed` is frame-step based, not duration based. The same setting feels different at different OBS frame rates.
2. The animation interpolates from the current crop every tick rather than from a captured start state to a target state. This makes the curve harder to reason about.
3. Zoom-in and zoom-out share the same duration and easing behavior.

### Baseline Strengths

The baseline script already satisfied several natural-motion principles:

| Guide Principle | Current Status | Notes |
|-----------------|----------------|-------|
| Zoom toward clear target | Mostly implemented | The target is the mouse position. |
| Avoid linear motion | Implemented | Uses cubic ease-in-out. |
| Unified visual layer | Implemented | Moves the captured source as one Crop/Pad layer. |
| Stable end state | Implemented | Stays zoomed until the user toggles out. |
| Predictable camera | Partially implemented | Follow safe zone helps, but timing is frame-dependent. |
| Avoid artificial wobble | Implemented | No rotation, shake, or fake layer delay. |

### Baseline Gaps

| Gap | Impact | Recommended Fix |
|-----|--------|-----------------|
| Frame-step speed | Zoom duration changes with OBS FPS. | Use elapsed time and duration in milliseconds. |
| Single easing curve | Cannot tune zoom-in vs zoom-out feel. | Add easing presets and separate in/out settings. |
| Center-only framing | Target always lands near the center. | Add configurable target framing bias, default `x=0.50`, `y=0.45`. |
| High default zoom | `2.0x` can feel aggressive for UI demos. | Use `1.45x` or add presets that set zoom amount. |
| No reduced motion | Some users may prefer minimal motion. | Add reduced-motion mode. |
| No pre-zoom cursor pause | Zoom can start while cursor is still moving fast. | Add optional cursor-stability delay. |
| No target rectangle | Cursor-only targeting cannot frame a whole UI region. | Add optional manual/external target rectangle later. |

## OBS Studio Constraints

### Crop/Pad Filter Uses Integer Settings

OBS's built-in Crop/Pad filter stores crop values as integers:

- `left`
- `top`
- `right`
- `bottom`
- `cx`
- `cy`

The Lua script also floors the crop values before applying them. This means the current approach cannot produce true subpixel crop animation.

This is acceptable for a first natural-motion pass. Natural easing, duration control, and better target framing will matter more than subpixel interpolation.

### Lua Timers Are Frame-Bound in Practice

OBS Lua timers are processed from OBS's tick path. Updating the timer faster than the video frame rate will not create visible sub-frame smoothness. The right fix is elapsed-time animation, not shorter timer intervals.

### Best Boundary

Keep the first implementation Lua-only. Changing OBS Studio or writing a custom plugin is only justified if the project later needs:

- Fractional crop coordinates
- Shader-based zoom
- Motion blur
- Automatic UI-element recognition
- Native click detection
- Custom high-quality sampling beyond OBS scene scale filtering

## Guide Feasibility Matrix

| Guide Item | Fit for This Project | Implementation Notes |
|------------|----------------------|----------------------|
| Clear target | Strong | Mouse position is already the default target. Target rectangles can be added later. |
| Avoid linear motion | Strong | Add easing presets and keep professional curves as defaults. |
| Soft starts/endings | Strong | Use duration-based animation and start/end crop snapshots. |
| Translation only when helpful | Strong | Compute destination crop from target and clamp to source bounds. |
| Stable end state | Strong | Already stable; add optional post-zoom hold only if auto-zoom-out is introduced. |
| Careful overshoot | Medium | Can be implemented, but should default off. |
| No fake layer lag | Strong | Current single-source crop model is ideal. |
| Coordinate with cursor movement | Medium | Cursor stability delay is possible; click detection is not currently available. |
| Zoom amount based on readability | Strong | Add presets and better defaults. |
| Predictable behavior | Strong | Add camera model and deterministic transitions. |
| Reduced motion | Strong | Add a mode that shortens duration and lowers zoom factor. |
| Avoid blur/artifacts | Medium | Cap default zoom, recommend scale filtering, avoid jitter. |
| Camera model | Strong | Maps naturally to crop state and zoom factor. |
| Derive camera from target | Strong | Current target math can be generalized. |
| Sensible defaults | Strong | Add preset dropdowns. |

## Proposed Design

### Design Principle

Represent zoom as a camera transition, then convert the camera state into OBS Crop/Pad settings.

For this script, the simplest camera state is still crop-based:

```lua
CameraState = {
    x = number,
    y = number,
    w = number,
    h = number,
}
```

This avoids a risky rewrite while still making the animation predictable.

Later, this can be wrapped in a semantic camera model:

```lua
CameraState = {
    center_x = number,
    center_y = number,
    zoom = number,
}
```

The first pass should use crop state because it matches the current implementation and OBS filter contract.

### Animation State

Add a dedicated animation object:

```lua
animation = {
    active = false,
    kind = "zoom_in" or "zoom_out" or "follow",
    from = { x = 0, y = 0, w = 0, h = 0 },
    to = { x = 0, y = 0, w = 0, h = 0 },
    elapsed_ms = 0,
    duration_ms = 420,
    easing = "ease_out_cubic",
}
```

Each frame:

1. Advance `elapsed_ms` by the actual frame delta.
2. Compute `t = clamp(0, 1, elapsed_ms / duration_ms)`.
3. Compute `e = apply_easing(easing, t)`.
4. Interpolate from `animation.from` to `animation.to`.
5. Apply the resulting crop.

This produces consistent motion at 30 FPS, 60 FPS, and variable frame rates.

### Easing Presets

Add these easing options:

| ID | Intended Use |
|----|--------------|
| `ease_out_cubic` | Best default for quick focus zooms. |
| `ease_in_out_cubic` | Best default for tutorial-style zooms. |
| `ease_out_quart` | Slightly more energetic marketing/demo feel. |
| `ease_in_out_quart` | Slower, polished large movement. |
| `linear` | Debugging only, not recommended. |

Default recommendation:

- Zoom in: `ease_out_cubic`
- Zoom out: `ease_in_out_cubic`
- Follow: keep current smoothing model, then revisit after zoom animation is stable.

### Presets

Add a `Motion Preset` dropdown:

| Preset | Zoom Factor | Zoom In | Zoom Out | Easing | Notes |
|--------|-------------|---------|----------|--------|-------|
| Tutorial | `1.45x` | `420ms` | `320ms` | ease-out/ease-in-out cubic | Recommended default. |
| Quick Focus | `1.35x` | `280ms` | `240ms` | ease-out cubic | Fast but not abrupt. |
| Detailed Inspection | `1.75x` | `500ms` | `360ms` | ease-in-out cubic | For code/text close-up. |
| Energetic Demo | `1.60x` | `350ms` | `260ms` | ease-out quart | Polished but still professional. |
| Reduced Motion | `1.15x` | `100ms` | `100ms` | ease-out cubic | Minimal movement. |
| Custom | User-defined | User-defined | User-defined | User-defined | Exposes all controls. |

The preset should populate settings, but the script should preserve custom overrides when `Custom` is selected.

### Target Framing Bias

Current behavior effectively centers the mouse in the zoomed area. The guide suggests placing targets slightly above center, which often works better for tutorials and captions.

Add:

```lua
target_screen_x = 0.50
target_screen_y = 0.45
```

Destination crop:

```lua
crop.x = target_x - new_size.width * target_screen_x
crop.y = target_y - new_size.height * target_screen_y
```

Clamp the crop to source bounds as the script already does.

Default:

- `target_screen_x = 0.50`
- `target_screen_y = 0.45`

Expose these as advanced settings only if needed. In the first implementation, constants are enough.

### Cursor Stability Delay

Implemented enhancement:

1. User presses zoom hotkey.
2. Script samples cursor movement for `150ms` by default.
3. If cursor is stable enough, start zoom.
4. If cursor keeps moving, wait up to the `250ms` default cap, then zoom to the latest position.

This makes zooms feel intentional while bounding the added latency. The delay can be disabled through the `Cursor settle before zoom` group.

### Overshoot

Overshoot should not be a default for this project. If implemented, it should be subtle and preset-controlled:

- Off by default
- Maximum effective scale overshoot: `1-2%`
- Only for `Energetic Demo`

Because the script animates crop width/height, overshoot means temporarily making the crop slightly smaller than the target crop, then settling back.

## Implementation Plan

### Phase 1: Deterministic Natural Zoom

Scope:

1. Add easing functions.
2. Add animation state.
3. Replace `zoom_time += zoom_speed` with elapsed-time animation.
4. Add separate zoom-in and zoom-out duration defaults.
5. Capture start crop when animation starts.
6. Interpolate from captured start crop to target crop.
7. Preserve existing hotkey behavior and follow behavior.

Expected result:

- Same feature set as today.
- More consistent animation across frame rates.
- Smooth, predictable zoom-in and zoom-out.

Stop condition:

- Zoom in/out works with the selected source.
- Existing follow behavior still works after zooming in.
- Zoom out restores the original full crop.

### Phase 2: Professional Defaults and Presets

Scope:

1. Add motion preset setting.
2. Change default zoom factor to a natural tutorial default.
3. Add separate in/out easing settings.
4. Add reduced-motion preset.
5. Add target framing bias.

Expected result:

- Users can choose a natural motion style without tuning low-level controls.
- Default behavior is less aggressive and more tutorial-friendly.

Stop condition:

- Presets update settings predictably.
- Custom settings remain possible.
- Old saved settings do not break script loading.

### Phase 3: Cursor Coordination

Status: Implemented in the current branch.

Scope:

1. Add optional cursor-stability delay.
2. Add maximum pre-zoom wait.
3. Add debug logging for delay decisions.

Expected result:

- Zoom starts after the cursor has settled near the intended target.
- Fast cursor travel no longer triggers a camera move that feels accidental.

Stop condition:

- Cursor delay can be disabled.
- Delay does not make hotkeys feel unresponsive.
- Debug logs explain when the script waits and when it starts.

### Phase 4: Optional Advanced Polish

Scope:

1. Add subtle overshoot option for energetic demos.
2. Add optional target rectangle input path for remote/control integrations.
3. Consider storing scale filter preference or documenting recommended OBS scale filter.

Expected result:

- More creative styles are available without compromising professional defaults.

Stop condition:

- Professional presets remain bounce-free.
- Overshoot is visibly subtle when enabled.

## Backward Compatibility

The current `zoom_speed` and `follow_speed` settings should not be removed abruptly.

Recommended compatibility approach:

1. Keep `follow_speed` unchanged in the first phase.
2. Replace visible `Zoom Speed` with `Zoom In Duration` and `Zoom Out Duration`.
3. On load, if the profile has legacy `zoom_value` or `zoom_speed` settings but no explicit `motion_preset`, mark the preset as `Custom`. This avoids showing `Tutorial` beside an older aggressive value such as `2.0x`.
4. If a future migration chooses to convert old `zoom_speed` into duration values, use an approximate mapping:

```lua
duration_ms = frame_interval_ms * math.ceil(1 / zoom_speed)
```

For example, at 60 FPS:

| Old `zoom_speed` | Approx Frames | Approx Duration |
|------------------|---------------|-----------------|
| `0.10` | 10 | 167ms |
| `0.06` | 17 | 283ms |
| `0.03` | 34 | 567ms |

The current default `0.06` maps to about `280ms` at 60 FPS, which is a little fast but still within the guide's quick-focus range.

## Testing Plan

### Manual OBS Tests

1. Add a Display Capture source.
2. Select it as the Zoom Source.
3. Test zoom in/out at default preset.
4. Test zoom near each corner and edge.
5. Test zoom with auto-follow enabled.
6. Test zoom with auto-follow disabled.
7. Test scene switching while zoomed.
8. Test script reload while zoomed.
9. Test with an existing Crop/Pad filter.
10. Test with manual source position enabled.

### Motion Quality Tests

1. Record a short 30 FPS clip.
2. Record a short 60 FPS clip.
3. Compare perceived zoom duration.
4. Confirm the target settles without visible bounce in professional presets.
5. Confirm text is readable after the zoom settles.
6. Confirm zoom-out does not feel abrupt.

### Regression Tests

1. macOS Retina display mapping still centers correctly.
2. Multi-monitor offsets still work.
3. Remote mouse socket mode still supplies target coordinates.
4. Non-display capture with manual override still behaves as before.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Animation refactor breaks follow behavior | Keep follow path unchanged in Phase 1 except for shared crop application. |
| Settings migration surprises users | Preserve old settings and log conversion when debug logging is enabled. |
| More settings make UI noisy | Use presets first; hide advanced knobs unless custom mode is selected. |
| Duration feels laggy | Use tutorial-friendly defaults and allow Quick Focus preset. |
| Integer crop causes small jitter | Use elapsed-time animation, clamp consistently, and avoid over-zoom defaults. |

## Recommendation

Proceed with a Lua-only implementation first. The highest-value changes are duration-based animation, easing presets, captured start/end crop states, better defaults, and target framing bias.

Do not modify OBS Studio for the first pass. OBS source-code findings show that the current Crop/Pad route has integer crop limits and frame-bound update timing, but those limits do not prevent a much more natural zoom feel. A custom OBS filter or shader should remain a later option only if Lua-level improvements are not enough.
