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
| Phase 4A target rectangle support | Complete | Static contract tests and LuaJIT math tests verify source-coordinate rectangle crop derivation, edge clamping, large-rectangle behavior, and legacy point targeting. |
| Phase 4B/4C scale-filter helper and overshoot | Deferred | These remain optional and should stay disabled by default unless recorded output proves the need. |

Verification commands used for the current pass:

```bash
luajit tests/obs_lua_smoke.lua
luajit tests/obs_lua_target_rect.lua
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

Status: Researched against the local OBS Studio source checkout. Phase 4A target-rectangle support is implemented in the current branch; scale-filter automation, overshoot, timer/tick rewiring, and custom shader/plugin work remain optional and deferred until recorded validation proves they are needed.

OBS source-code findings below use paths relative to the OBS Studio source root:

| Area | Source Evidence | Practical Meaning |
|------|-----------------|-------------------|
| Crop/Pad filter contract | `plugins/obs-filters/crop-filter.c:69-80` reads `relative`, `left`, `top`, `right`, `bottom`, `cx`, and `cy` from filter settings. `plugins/obs-filters/crop-filter.c:122-156` converts those settings into shader UV scale/offset values. `plugins/obs-filters/crop-filter.c:285-296` registers the filter as `crop_filter` with video tick/render callbacks. | The current Lua strategy is aligned with OBS's built-in filter model. Phase 4 does not need an OBS Studio source patch for target rectangles, overshoot, or better timing behavior. |
| Crop precision limit | `plugins/obs-filters/crop-filter.c:73-79` casts settings to integers, and the filter properties expose integer controls in `plugins/obs-filters/crop-filter.c:106-111`. | Lua-side polish remains integer crop animation. This is acceptable for natural screen-recording zooms, but it means Phase 4 should not promise subpixel camera movement. |
| Crop rendering path | `plugins/obs-filters/data/crop_filter.effect:6-15` uses `mul_val` and `add_val` with a linear sampler, and `plugins/obs-filters/crop-filter.c:217-244` renders the filtered output at the computed crop width and height. | Overshoot and rectangle framing should be expressed as crop rectangles. A custom shader/plugin is only justified if recorded output shows text softness or jitter that cannot be solved with sane zoom limits and scene scale filtering. |
| Source update path | `libobs/obs-source.c:1066-1080` applies settings through `obs_source_update` and defers video-source updates into OBS's update path. | Updating the Crop/Pad filter settings from Lua is a normal OBS API path. The current implementation can stay with `obs_source_update`. |
| Scene item scale filters | `libobs/obs.h:124-130` defines `OBS_SCALE_DISABLE`, `POINT`, `BICUBIC`, `BILINEAR`, `LANCZOS`, and `AREA`. `libobs/obs.h:1812-1813` exports `obs_sceneitem_set_scale_filter` and `obs_sceneitem_get_scale_filter`. `libobs/obs-scene.c:754-774` selects bicubic, lanczos, or area effects during scene item rendering. | Scale-filter polish is available at the scene-item layer, not inside the Crop/Pad filter itself. It can improve the final stretch of the cropped source, but changing it mutates scene item state and must be opt-in or documentation-only. |
| Scale filter persistence and UI | `libobs/obs-scene.c:1214-1227` loads the scene item's `scale_filter` string, and `libobs/obs-scene.c:1380-1393` saves it. `frontend/widgets/OBSBasic_SceneItems.cpp:377-393` exposes the same choices in the OBS scale filtering menu. | The report should treat scale filtering as a user-visible OBS setting. If the script ever sets it automatically, it should preserve the previous value and restore it on release, or clearly document the persistent change. |
| Lua scripting callbacks | `shared/obs-scripting/obs-scripting-lua.c:308-320` implements `timer_add` using OBS video-frame time. `shared/obs-scripting/obs-scripting-lua.c:1039-1080` processes Lua timers from the script tick path. `shared/obs-scripting/obs-scripting-lua.c:1008-1022` exposes timers plus tick and main-render callbacks to Lua. | The current timer-based animation is appropriate for Phase 4. A tick callback can be considered if recorded output shows timer jitter, but a main-render callback is unnecessary unless we build a custom renderer or overlay. |
| Lua binding breadth | `shared/obs-scripting/obslua/obslua.i:14` includes `obs.h`, and `shared/obs-scripting/obslua/obslua.i:100` includes it for SWIG generation. | The scene-item scale-filter APIs are likely exposed to Lua, but the implementation must verify symbol availability in this project's OBS Lua smoke test before relying on them. |

Scope:

1. Add an optional target-rectangle camera path for remote/control integrations.
2. Document OBS scale-filter recommendations, then optionally add an opt-in scale-filter helper.
3. Add a subtle overshoot option only for energetic demos.
4. Defer custom shader/plugin work unless recorded output proves that the Crop/Pad path is the limiting factor.

Recommended implementation order:

1. Target rectangle support

   Status: Implemented in the current branch.

   This is the most useful Phase 4 item and stays fully Lua-side.

   Add a semantic target model:

   ```lua
   Target = {
       kind = "point" or "rect",
       x = number,
       y = number,
       w = number,
       h = number,
       coordinate_space = "source",
   }
   ```

   For a rectangle target, derive the destination crop from the rectangle instead of only from the cursor point:

   ```lua
   local source_aspect = source_width / source_height
   local margin = target_rect_margin or 1.18

   local min_w = target.w * margin
   local min_h = target.h * margin
   local crop_w = math.max(source_width / zoom_value, min_w, min_h * source_aspect)

   crop_w = clamp(1, source_width, crop_w)
   local crop_h = crop_w / source_aspect

   local anchor_x = target.x + target.w * 0.5
   local anchor_y = target.y + target.h * 0.5

   crop.x = anchor_x - crop_w * target_screen_x
   crop.y = anchor_y - crop_h * target_screen_y
   crop = clamp_crop_to_source_bounds(crop)
   ```

   Notes:

   - Keep `point` targets as the default path.
   - Let remote/socket integrations provide rectangles in source coordinates first. The implemented UDP format is `rect x y width height`; the legacy `x y` point format still works.
   - Avoid trying to infer UI elements from OBS; OBS sees captured pixels, not semantic app controls.
   - Use the existing target framing bias so rectangles can settle slightly above center.
   - If edge clamping moves the rectangle away from the requested bias, prefer keeping the whole rectangle visible over preserving the exact bias.
   - Contract tests cover aspect-ratio preservation, large rectangles, edge rectangles, and cursor-point behavior remaining unchanged.

2. OBS scale-filter guidance and optional helper

   The first deliverable should be documentation, not automatic mutation.

   Recommended user-facing guidance:

   - For normal software recordings, try `Lanczos` for sharper text when the scene item is being scaled.
   - Try `Bicubic` if `Lanczos` looks too sharp or creates ringing around text.
   - Avoid `Point` unless recording pixel art.
   - `Area` is mainly useful for strong downscaling, not the primary zoom-in readability case.

   Optional script helper, if implemented:

   ```lua
   scale_filter_policy = "leave_unchanged" -- default
   -- other possible values:
   -- "recommend_in_log"
   -- "temporarily_set_lanczos"
   -- "temporarily_set_bicubic"
   ```

   Implementation guardrails:

   - Verify `obs.obs_sceneitem_get_scale_filter`, `obs.obs_sceneitem_set_scale_filter`, and `obs.OBS_SCALE_LANCZOS` in the Lua smoke test before adding the setting.
   - Store the original scene-item filter before changing it.
   - Restore the original value in `release_sceneitem`, script unload, and source change paths.
   - Keep the default as `leave_unchanged`, because OBS persists scene item scale filters in scene data.
   - Add debug logging that says whether the script left the filter alone, recommended a value, or temporarily changed it.

3. Subtle overshoot

   Overshoot should remain style-specific, not professional-default behavior.

   Suggested settings:

   ```lua
   overshoot_mode = "off" -- default
   overshoot_percent = 1.0
   overshoot_settle_ratio = 0.18
   ```

   Recommended algorithm:

   1. Compute the normal final target crop.
   2. Compute the target anchor from the final crop and the target bias:

      ```lua
      anchor_x = final_crop.x + final_crop.w * target_screen_x
      anchor_y = final_crop.y + final_crop.h * target_screen_y
      ```

   3. Convert scale overshoot into a slightly smaller crop:

      ```lua
      local overshoot_scale = 1.0 + overshoot_percent / 100.0
      overshoot_crop.w = final_crop.w / overshoot_scale
      overshoot_crop.h = final_crop.h / overshoot_scale
      overshoot_crop.x = anchor_x - overshoot_crop.w * target_screen_x
      overshoot_crop.y = anchor_y - overshoot_crop.h * target_screen_y
      ```

   4. Clamp the overshoot crop to source bounds.
   5. If clamping shifts the anchor noticeably, skip overshoot for that move. This avoids odd edge bounce near screen borders.
   6. Animate in two segments:

      | Segment | Duration | Target | Easing |
      |---------|----------|--------|--------|
      | Approach | `82%` of zoom-in duration | Overshoot crop | `ease_out_quart` |
      | Settle | `18%` of zoom-in duration | Final crop | `ease_out_cubic` |

   Guardrails:

   - Enable only for `Energetic Demo` or a hidden advanced/custom setting.
   - Cap overshoot at `1-2%`.
   - Do not use bounce or elastic easing curves for professional presets.
   - Do not overshoot zoom-out by default.
   - Validate with a short recorded clip, because overshoot can look acceptable in preview but distracting after encoding.

4. Timer/tick polish

   Keep the existing `timer_add` path unless recorded evidence shows inconsistent frame pacing. OBS processes Lua timers from the script tick path using video-frame time, so shorter timer intervals cannot create visible sub-frame smoothness.

   If a later recording shows timer jitter:

   - Move animation advancement into a single `script_tick(seconds)` or `obs_add_tick_callback` path.
   - Keep the same `camera_animation.elapsed_ms` model.
   - Avoid `obs_add_main_render_callback` unless the script starts drawing its own overlay or custom render pass.

5. Custom shader/plugin route

   Defer this. OBS's Crop/Pad filter already renders through a simple shader with linear sampling, and the current script can achieve the natural-motion guide's main goals without a native plugin.

   Only revisit a native filter/plugin if all of these are true:

   - Recorded output still shows unacceptable text softness or integer-pixel jitter.
   - The problem reproduces after sane zoom caps, stable end frames, and scene scale-filter tuning.
   - The project explicitly needs fractional crop coordinates or custom sampler control.
   - The added install/build burden is acceptable.

Expected result:

- Remote/control integrations can frame a whole UI region instead of only a cursor point.
- OBS scale-filter behavior is documented clearly, with an opt-in helper available only if Lua binding verification passes.
- Energetic demos can get a tiny sense of polish without introducing visible bounce into tutorial/professional presets.
- The project keeps the low-maintenance Lua-only architecture unless recorded evidence justifies a native OBS plugin.

Stop condition:

- Professional presets remain bounce-free.
- `Tutorial`, `Quick Focus`, `Detailed Inspection`, and `Reduced Motion` never enable overshoot implicitly.
- Target rectangles keep the requested rectangle visible after clamping.
- Scale-filter helper defaults to no mutation and restores any temporary change.
- Lua smoke tests cover any new OBS API symbols before the script depends on them.
- Recorded validation shows no distracting bounce, edge snap, or text-quality regression after export.

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
3. Remote mouse socket mode still supplies point coordinates.
4. Remote rectangle socket mode supplies source-coordinate target rectangles and keeps the rectangle visible after clamping.
5. Non-display capture with manual override still behaves as before.

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
