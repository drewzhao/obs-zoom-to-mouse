-- Focused LuaJIT checks for Phase 4 target-rectangle crop math.

local obs_stub = {}

setmetatable(obs_stub, {
    __index = function(_, key)
        if key == "obs_get_version_string" then
            return function()
                return "30.0.0"
            end
        end

        if key == "obs_get_frame_interval_ns" then
            return function()
                return 16666667
            end
        end

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

local zoom = {
    zoom_to = 1.45,
    source_size = { width = 1920, height = 1080 },
    source_crop_filter = { x = 0, y = 0, w = 1920, h = 1080 },
}

local centered = get_target_position_for_target(zoom, {
    kind = "rect",
    x = 840,
    y = 450,
    w = 240,
    h = 120,
    coordinate_space = "source",
})

assert_close(centered.crop.w, 1920 / 1.45, 0.001, "centered crop width")
assert_close(centered.crop.h, (1920 / 1.45) / (1920 / 1080), 0.001, "centered crop height")
assert_close(centered.crop.x, math.floor(960 - centered.crop.w * 0.50), 0.001, "centered crop x")
assert_close(centered.crop.y, math.floor(510 - centered.crop.h * 0.45), 0.001, "centered crop y")
assert(centered.raw_center.x == 960, "centered raw x should be rectangle center")
assert(centered.raw_center.y == 510, "centered raw y should be rectangle center")

local edge = get_target_position_for_target(zoom, {
    kind = "rect",
    x = 1400,
    y = 780,
    w = 240,
    h = 120,
    coordinate_space = "source",
})

assert(edge.crop.x <= 1400, "edge crop should include rectangle left")
assert(edge.crop.x + edge.crop.w >= 1640, "edge crop should include rectangle right")
assert(edge.crop.y <= 780, "edge crop should include rectangle top")
assert(edge.crop.y + edge.crop.h >= 900, "edge crop should include rectangle bottom")

local large = get_target_position_for_target({
    zoom_to = 2.0,
    source_size = { width = 1920, height = 1080 },
    source_crop_filter = { x = 0, y = 0, w = 1920, h = 1080 },
}, {
    kind = "rect",
    x = 20,
    y = 20,
    w = 1880,
    h = 1040,
    coordinate_space = "source",
})

assert_close(large.crop.x, 0, 0.001, "large crop x")
assert_close(large.crop.y, 0, 0.001, "large crop y")
assert_close(large.crop.w, 1920, 0.001, "large crop width")
assert_close(large.crop.h, 1080, 0.001, "large crop height")

get_mouse_pos = function()
    return { x = 960, y = 540 }
end

local point = get_target_position(zoom)

assert_close(point.crop.w, centered.crop.w, 0.001, "point crop width")
assert_close(point.crop.x, math.floor(960 - point.crop.w * 0.50), 0.001, "point crop x")
assert_close(point.crop.y, math.floor(540 - point.crop.h * 0.45), 0.001, "point crop y")

print("OBS Lua target rectangle tests passed")
