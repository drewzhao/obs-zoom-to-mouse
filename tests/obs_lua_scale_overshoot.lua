-- Focused LuaJIT checks for Phase 4B scale filtering and Phase 4C overshoot.

local obs_stub = {
    OBS_LOG_INFO = 1,
    OBS_SCALE_DISABLE = 0,
    OBS_SCALE_POINT = 1,
    OBS_SCALE_BICUBIC = 2,
    OBS_SCALE_BILINEAR = 3,
    OBS_SCALE_LANCZOS = 4,
    OBS_SCALE_AREA = 5,
}

local logs = {}

function obs_stub.obs_get_version_string()
    return "30.0.0"
end

function obs_stub.obs_get_frame_interval_ns()
    return 16666667
end

function obs_stub.obs_sceneitem_get_scale_filter(item)
    return item.scale_filter
end

function obs_stub.obs_sceneitem_set_scale_filter(item, value)
    item.scale_filter = value
    item.set_count = (item.set_count or 0) + 1
end

function obs_stub.script_log(_, message)
    table.insert(logs, message)
end

setmetatable(obs_stub, {
    __index = function()
        return function()
            return nil
        end
    end
})

_G.obslua = obs_stub

dofile("obs-zoom-to-mouse.lua")

local function assert_close(actual, expected, tolerance, label)
    if math.abs(actual - expected) > tolerance then
        error(label .. ": expected " .. tostring(expected) .. ", got " .. tostring(actual), 2)
    end
end

local item = { scale_filter = obs_stub.OBS_SCALE_BILINEAR, set_count = 0 }
local applied = apply_scale_filter_policy_to_item(item, "temporarily_set_lanczos")

assert(applied.applied == true, "Lanczos policy should apply")
assert(applied.original_filter == obs_stub.OBS_SCALE_BILINEAR, "Original filter should be captured")
assert(item.scale_filter == obs_stub.OBS_SCALE_LANCZOS, "Item should be set to Lanczos")

local restored = restore_scale_filter_policy_for_item(item, applied)

assert(restored == true, "Applied scale filter should restore")
assert(item.scale_filter == obs_stub.OBS_SCALE_BILINEAR, "Item should restore original filter")

item.scale_filter = obs_stub.OBS_SCALE_LANCZOS
local active_restore = restore_scale_filter_policy_for_item(item, {
    active = true,
    original_filter = obs_stub.OBS_SCALE_BICUBIC,
})

assert(active_restore == true, "Active global restore state should restore")
assert(item.scale_filter == obs_stub.OBS_SCALE_BICUBIC, "Active global restore state should restore original filter")

local unchanged = apply_scale_filter_policy_to_item(item, "leave_unchanged")

assert(unchanged.applied == false, "Leave-unchanged policy must not mutate")
assert(item.scale_filter == obs_stub.OBS_SCALE_BICUBIC, "Leave-unchanged policy should preserve filter")

local recommended = apply_scale_filter_policy_to_item(item, "recommend_in_log")

assert(recommended.applied == false, "Recommendation policy must not mutate")
assert(#logs > 0, "Recommendation policy should log guidance")

local zoom = {
    zoom_to = 1.6,
    source_size = { width = 1920, height = 1080 },
    source_crop_filter = { x = 0, y = 0, w = 1920, h = 1080 },
}

local final_crop = {
    x = 360,
    y = 200,
    w = 1200,
    h = 675,
}

local overshoot = build_overshoot_crop(zoom, final_crop, 1.0)

assert(overshoot ~= nil, "Centered final crop should allow overshoot")
assert(overshoot.w < final_crop.w, "Overshoot crop should be narrower")
assert(overshoot.h < final_crop.h, "Overshoot crop should be shorter")

local final_anchor_x = final_crop.x + final_crop.w * 0.50
local final_anchor_y = final_crop.y + final_crop.h * 0.45
local overshoot_anchor_x = overshoot.x + overshoot.w * 0.50
local overshoot_anchor_y = overshoot.y + overshoot.h * 0.45

assert_close(overshoot_anchor_x, final_anchor_x, 1.0, "Overshoot anchor x")
assert_close(overshoot_anchor_y, final_anchor_y, 1.0, "Overshoot anchor y")

local options = create_overshoot_animation_options(zoom, final_crop, 350, "subtle", 1.0, 0.18)

assert(options ~= nil, "Subtle overshoot should create animation options")
assert(options.approach_duration_ms == 287, "Approach duration should be 82 percent")
assert(options.settle_duration_ms == 63, "Settle duration should be 18 percent")
assert(options.approach_to.w < final_crop.w, "Approach target should be overshot")
assert(options.settle_to.w == final_crop.w, "Settle target should return to final crop")

local off_options = create_overshoot_animation_options(zoom, final_crop, 350, "off", 1.0, 0.18)

assert(off_options == nil, "Off overshoot mode should not create animation options")

print("OBS Lua scale filter and overshoot tests passed")
