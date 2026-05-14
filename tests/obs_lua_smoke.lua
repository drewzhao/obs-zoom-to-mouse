-- Minimal LuaJIT smoke loader for the OBS script.
--
-- This does not emulate OBS. It only stubs enough of obslua for the script to
-- load and define its functions, which catches syntax errors and top-level
-- dependency mistakes before testing inside OBS.

local obs_stub = {}

setmetatable(obs_stub, {
    __index = function(_, key)
        if key == "obs_get_version_string" then
            return function()
                return "30.0.0"
            end
        end

        return function()
            return nil
        end
    end
})

_G.obslua = obs_stub

dofile("obs-zoom-to-mouse.lua")

assert(type(script_description) == "function", "script_description should be defined")
assert(type(script_properties) == "function", "script_properties should be defined")
assert(type(script_load) == "function", "script_load should be defined")
assert(type(script_update) == "function", "script_update should be defined")
assert(type(script_unload) == "function", "script_unload should be defined")

print("OBS Lua smoke load passed")
