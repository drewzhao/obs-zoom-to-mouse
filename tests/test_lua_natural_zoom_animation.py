import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LUA_SCRIPT = ROOT / "obs-zoom-to-mouse.lua"
REPORT = ROOT / "docs" / "LUA_SCRIPT_DESIGN_AND_ARCHITECTURE.md"


def read_lua() -> str:
    return LUA_SCRIPT.read_text(encoding="utf-8")


class NaturalZoomAnimationLuaTests(unittest.TestCase):
    def test_design_report_records_reference_conformance_target(self):
        report = REPORT.read_text(encoding="utf-8")

        self.assertIn("Approximately 80-85% of the guide", report)
        self.assertIn("duration-based animation", report)
        self.assertIn("target framing bias", report)

    def test_lua_declares_natural_motion_settings_and_presets(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+MotionPreset\s*=\s*\{")
        self.assertRegex(lua, r"Tutorial\s*=\s*\"tutorial\"")
        self.assertRegex(lua, r"ReducedMotion\s*=\s*\"reduced_motion\"")
        self.assertRegex(lua, r"local\s+Easing\s*=\s*\{")
        self.assertRegex(lua, r"EaseOutCubic\s*=\s*\"ease_out_cubic\"")
        self.assertRegex(lua, r"EaseInOutCubic\s*=\s*\"ease_in_out_cubic\"")
        self.assertRegex(lua, r"local\s+motion_preset\s*=\s*MotionPreset\.Tutorial")
        self.assertRegex(lua, r"local\s+zoom_in_duration_ms\s*=\s*420")
        self.assertRegex(lua, r"local\s+zoom_out_duration_ms\s*=\s*320")
        self.assertRegex(lua, r"local\s+zoom_in_easing\s*=\s*Easing\.EaseOutCubic")
        self.assertRegex(lua, r"local\s+zoom_out_easing\s*=\s*Easing\.EaseInOutCubic")

    def test_lua_uses_camera_animation_instead_of_frame_step_zoom_time(self):
        lua = read_lua()

        self.assertNotIn("zoom_time = zoom_time + zoom_speed", lua)
        self.assertRegex(lua, r"local\s+camera_animation\s*=\s*\{")
        self.assertRegex(lua, r"function\s+start_crop_animation\s*\(")
        self.assertRegex(lua, r"function\s+update_crop_animation\s*\(")
        self.assertRegex(lua, r"camera_animation\.elapsed_ms\s*=\s*camera_animation\.elapsed_ms\s*\+\s*elapsed_ms")
        self.assertRegex(lua, r"local\s+t\s*=\s*clamp\(0,\s*1,\s*camera_animation\.elapsed_ms\s*/\s*camera_animation\.duration_ms\)")
        self.assertRegex(lua, r"local\s+eased\s*=\s*apply_easing\(camera_animation\.easing,\s*t\)")
        self.assertRegex(lua, r"start_crop_animation\(ZoomState\.ZoomingIn")
        self.assertRegex(lua, r"start_crop_animation\(ZoomState\.ZoomingOut")

    def test_lua_exposes_natural_motion_controls_in_obs_properties(self):
        lua = read_lua()

        self.assertIn('"Motion Preset"', lua)
        self.assertIn('"Zoom In Duration (ms)"', lua)
        self.assertIn('"Zoom Out Duration (ms)"', lua)
        self.assertIn('"Zoom In Easing"', lua)
        self.assertIn('"Zoom Out Easing"', lua)
        self.assertNotIn('"Zoom Speed"', lua)

    def test_lua_marks_legacy_saved_motion_as_custom(self):
        lua = read_lua()

        self.assertRegex(lua, r"function\s+migrate_legacy_motion_preset\s*\(")
        self.assertIn('settings_has_user_value(settings, "motion_preset")', lua)
        self.assertIn('settings_has_user_value(settings, "zoom_value")', lua)
        self.assertIn('settings_has_user_value(settings, "zoom_speed")', lua)
        self.assertIn('obs.obs_data_set_string(settings, "motion_preset", MotionPreset.Custom)', lua)
        self.assertRegex(lua, r"function\s+script_load\s*\(settings\)[\s\S]*migrate_legacy_motion_preset\(settings\)")
        self.assertRegex(lua, r"function\s+script_update\s*\(settings\)[\s\S]*migrate_legacy_motion_preset\(settings\)")

    def test_lua_uses_target_framing_bias_for_zoom_destination(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+target_screen_x\s*=\s*0\.50")
        self.assertRegex(lua, r"local\s+target_screen_y\s*=\s*0\.45")
        self.assertRegex(lua, r"x\s*=\s*point\.x\s*-\s*new_size\.width\s*\*\s*target_screen_x")
        self.assertRegex(lua, r"y\s*=\s*point\.y\s*-\s*new_size\.height\s*\*\s*target_screen_y")

    def test_lua_exposes_cursor_coordination_controls(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+use_cursor_stability_delay\s*=\s*true")
        self.assertRegex(lua, r"local\s+cursor_stability_duration_ms\s*=\s*150")
        self.assertRegex(lua, r"local\s+cursor_stability_max_wait_ms\s*=\s*250")
        self.assertRegex(lua, r"local\s+cursor_stability_threshold_px\s*=\s*4")
        self.assertIn('"Cursor settle before zoom "', lua)
        self.assertIn('"Cursor Stable Duration (ms)"', lua)
        self.assertIn('"Max Cursor Wait (ms)"', lua)
        self.assertIn('"Cursor Movement Threshold (px)"', lua)
        self.assertIn('obs.obs_data_set_default_bool(settings, "cursor_stability_delay", true)', lua)
        self.assertIn('obs.obs_data_set_default_int(settings, "cursor_stability_duration_ms", 150)', lua)
        self.assertIn('obs.obs_data_set_default_int(settings, "cursor_stability_max_wait_ms", 250)', lua)
        self.assertIn('obs.obs_data_set_default_int(settings, "cursor_stability_threshold_px", 4)', lua)
        self.assertIn('use_cursor_stability_delay = obs.obs_data_get_bool(settings, "cursor_stability_delay")', lua)
        self.assertIn('cursor_stability_duration_ms = obs.obs_data_get_int(settings, "cursor_stability_duration_ms")', lua)
        self.assertIn('cursor_stability_max_wait_ms = obs.obs_data_get_int(settings, "cursor_stability_max_wait_ms")', lua)
        self.assertIn('cursor_stability_threshold_px = obs.obs_data_get_int(settings, "cursor_stability_threshold_px")', lua)

    def test_lua_waits_for_cursor_stability_before_zooming_in(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+cursor_zoom_pending\s*=\s*\{")
        self.assertRegex(lua, r"function\s+start_pending_zoom_in\s*\(")
        self.assertRegex(lua, r"function\s+update_cursor_stability_delay\s*\(")
        self.assertRegex(lua, r"cursor_zoom_pending\.stable_ms\s*=\s*cursor_zoom_pending\.stable_ms\s*\+\s*elapsed_ms")
        self.assertRegex(lua, r"cursor_zoom_pending\.elapsed_ms\s*>=\s*cursor_stability_max_wait_ms")
        self.assertRegex(lua, r"function\s+begin_zoom_in\s*\([\s\S]*start_pending_zoom_in\(\)")
        self.assertRegex(lua, r"function\s+on_timer\s*\(elapsed_ms\)[\s\S]*update_cursor_stability_delay\(elapsed_ms\)")
        self.assertIn("Cursor stable", lua)
        self.assertIn("Cursor stability wait capped", lua)

    def test_lua_exposes_phase4_target_rectangle_support(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+TargetKind\s*=\s*\{")
        self.assertRegex(lua, r"Point\s*=\s*\"point\"")
        self.assertRegex(lua, r"Rect\s*=\s*\"rect\"")
        self.assertRegex(lua, r"local\s+target_rect_margin\s*=\s*1\.18")
        self.assertRegex(lua, r"function\s+get_target_position_for_target\s*\(")
        self.assertRegex(lua, r"function\s+get_rect_target_position\s*\(")
        self.assertIn('coordinate_space = "source"', lua)
        self.assertIn('data:match("^%s*rect%s+', lua)

    def test_lua_exposes_phase4_scale_filter_helper(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+ScaleFilterPolicy\s*=\s*\{")
        self.assertRegex(lua, r"LeaveUnchanged\s*=\s*\"leave_unchanged\"")
        self.assertRegex(lua, r"RecommendInLog\s*=\s*\"recommend_in_log\"")
        self.assertRegex(lua, r"TemporarilySetLanczos\s*=\s*\"temporarily_set_lanczos\"")
        self.assertRegex(lua, r"TemporarilySetBicubic\s*=\s*\"temporarily_set_bicubic\"")
        self.assertRegex(lua, r"local\s+scale_filter_policy\s*=\s*ScaleFilterPolicy\.LeaveUnchanged")
        self.assertRegex(lua, r"function\s+apply_scale_filter_policy_to_item\s*\(")
        self.assertRegex(lua, r"function\s+restore_scale_filter_policy_for_item\s*\(")
        self.assertRegex(lua, r"function\s+apply_scale_filter_policy\s*\(")
        self.assertRegex(lua, r"function\s+restore_scale_filter_policy\s*\(")
        self.assertIn('"Scale Filter Policy"', lua)
        self.assertIn('obs.obs_data_set_default_string(settings, "scale_filter_policy", ScaleFilterPolicy.LeaveUnchanged)', lua)
        self.assertIn('scale_filter_policy = normalize_scale_filter_policy(obs.obs_data_get_string(settings, "scale_filter_policy"))', lua)

    def test_lua_exposes_phase4_subtle_overshoot_controls(self):
        lua = read_lua()

        self.assertRegex(lua, r"local\s+OvershootMode\s*=\s*\{")
        self.assertRegex(lua, r"Off\s*=\s*\"off\"")
        self.assertRegex(lua, r"Subtle\s*=\s*\"subtle\"")
        self.assertRegex(lua, r"local\s+overshoot_mode\s*=\s*OvershootMode\.Off")
        self.assertRegex(lua, r"local\s+overshoot_percent\s*=\s*1\.0")
        self.assertRegex(lua, r"local\s+overshoot_settle_ratio\s*=\s*0\.18")
        self.assertRegex(lua, r"function\s+build_overshoot_crop\s*\(")
        self.assertRegex(lua, r"function\s+create_overshoot_animation_options\s*\(")
        self.assertRegex(lua, r"settle_to\s*=\s*copy_crop")
        self.assertRegex(lua, r"camera_animation\.settle_to")
        self.assertIn('"Zoom Overshoot"', lua)
        self.assertIn('"Overshoot Amount (%)"', lua)
        self.assertIn('obs.obs_data_set_default_string(settings, "overshoot_mode", OvershootMode.Off)', lua)
        self.assertIn('obs.obs_data_set_default_double(settings, "overshoot_percent", 1.0)', lua)
        self.assertRegex(lua, r"\[MotionPreset\.Tutorial\][\s\S]*overshoot_mode\s*=\s*OvershootMode\.Off")
        self.assertRegex(lua, r"\[MotionPreset\.QuickFocus\][\s\S]*overshoot_mode\s*=\s*OvershootMode\.Off")
        self.assertRegex(lua, r"\[MotionPreset\.DetailedInspection\][\s\S]*overshoot_mode\s*=\s*OvershootMode\.Off")
        self.assertRegex(lua, r"\[MotionPreset\.ReducedMotion\][\s\S]*overshoot_mode\s*=\s*OvershootMode\.Off")
        self.assertRegex(lua, r"\[MotionPreset\.EnergeticDemo\][\s\S]*overshoot_mode\s*=\s*OvershootMode\.Subtle")

    def test_lua_target_rectangle_math_when_luajit_available(self):
        if shutil.which("luajit") is None:
            self.skipTest("LuaJIT is not installed on this machine")

        result = subprocess.run(
            ["luajit", "tests/obs_lua_target_rect.lua"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("OBS Lua target rectangle tests passed", result.stdout)

    def test_lua_scale_filter_and_overshoot_when_luajit_available(self):
        if shutil.which("luajit") is None:
            self.skipTest("LuaJIT is not installed on this machine")

        result = subprocess.run(
            ["luajit", "tests/obs_lua_scale_overshoot.lua"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("OBS Lua scale filter and overshoot tests passed", result.stdout)

    def test_lua_has_no_merge_conflict_markers(self):
        lua = read_lua()

        self.assertNotIn("<<<<<<<", lua)
        self.assertNotIn("=======", lua)
        self.assertNotIn(">>>>>>>", lua)

    def test_lua_script_smoke_loads_with_luajit_when_available(self):
        if shutil.which("luajit") is None:
            self.skipTest("LuaJIT is not installed on this machine")

        result = subprocess.run(
            ["luajit", "tests/obs_lua_smoke.lua"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("OBS Lua smoke load passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
