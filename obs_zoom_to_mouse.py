"""
OBS Zoom to Mouse - Python Edition
Zoom a display capture source to focus on the mouse cursor.

Author: BlankSourceCode (original Lua version)
Python port with enhanced features.

Version: 2.0.0
"""

import sys
import os

# Add the script directory to path for importing zoom_core
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    import obspython as obs
except ImportError:
    # For development/testing outside OBS
    obs = None

from zoom_core import (
    MouseTracker,
    DisplayManager,
    ZoomController,
    ZoomState,
    ConfigManager,
    ZoomProfile,
)
from zoom_core.websocket_server import WebSocketServer, SimpleUDPServer

# Version
VERSION = "2.0.0"
CROP_FILTER_NAME = "obs-zoom-to-mouse-crop"

# Global state
mouse_tracker = None
display_manager = None
zoom_controller = None
config_manager = None
ws_server = None

# OBS-related state
source_name = ""
source = None
sceneitem = None
sceneitem_info_orig = None
sceneitem_crop_orig = None
crop_filter = None
crop_filter_temp = None
crop_filter_settings = None

# Settings
current_profile_name = "standard"
debug_logging = False
is_timer_running = False
is_obs_loaded = False


def log(msg):
    """Log a message to OBS script log."""
    if debug_logging and obs:
        obs.script_log(obs.LOG_INFO, str(msg))


def get_display_capture_info():
    """Get display capture source information for the current platform."""
    if sys.platform == 'win32':
        return {
            'source_id': 'monitor_capture',
            'source_id_fallback': None,
            'prop_id': 'monitor_id',
            'prop_type': 'string'
        }
    elif sys.platform.startswith('linux'):
        return {
            'source_id': 'pipewire-screen-capture-source',
            'source_id_fallback': 'xshm_input_v2',
            'source_id_legacy': 'xshm_input',
            'prop_id': 'screen',
            'prop_type': 'int'
        }
    elif sys.platform == 'darwin':
        return {
            'source_id': 'screen_capture',
            'source_id_fallback': 'display_capture',
            'prop_id': 'display_uuid',
            'prop_type': 'string'
        }
    return None


def is_display_capture(source_obj):
    """Check if a source is a display capture source."""
    if source_obj is None:
        return False
    
    dc_info = get_display_capture_info()
    if dc_info is None:
        return False
    
    source_type = obs.obs_source_get_id(source_obj)
    
    if source_type == dc_info['source_id']:
        return True
    if dc_info.get('source_id_fallback') and source_type == dc_info['source_id_fallback']:
        return True
    if dc_info.get('source_id_legacy') and source_type == dc_info['source_id_legacy']:
        return True
    
    return False


def get_monitor_info_from_source(source_obj):
    """Get monitor information from a display capture source."""
    if not is_display_capture(source_obj):
        return None
    
    dc_info = get_display_capture_info()
    if dc_info is None:
        return None
    
    props = obs.obs_source_properties(source_obj)
    if props is None:
        return None
    
    try:
        monitor_id_prop = obs.obs_properties_get(props, dc_info['prop_id'])
        if not monitor_id_prop:
            return None
        
        settings = obs.obs_source_get_settings(source_obj)
        if settings is None:
            return None
        
        try:
            # Get the selected monitor value
            if dc_info['prop_type'] == 'string':
                to_match = obs.obs_data_get_string(settings, dc_info['prop_id'])
            else:
                to_match = obs.obs_data_get_int(settings, dc_info['prop_id'])
            
            # Find matching monitor name
            item_count = obs.obs_property_list_item_count(monitor_id_prop)
            found_name = None
            
            for i in range(item_count):
                name = obs.obs_property_list_item_name(monitor_id_prop, i)
                if dc_info['prop_type'] == 'string':
                    value = obs.obs_property_list_item_string(monitor_id_prop, i)
                else:
                    value = obs.obs_property_list_item_int(monitor_id_prop, i)
                
                if value == to_match:
                    found_name = name
                    break
            
            if found_name:
                # Parse display name like "Monitor: 1920x1080 @ 0,0"
                import re
                
                # Try to extract dimensions and position
                size_match = re.search(r'(\d+)x(\d+)', found_name)
                pos_match = re.search(r'@\s*(-?\d+),(-?\d+)', found_name)
                
                if size_match:
                    width = int(size_match.group(1))
                    height = int(size_match.group(2))
                    x = int(pos_match.group(1)) if pos_match else 0
                    y = int(pos_match.group(2)) if pos_match else 0
                    
                    return {
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height,
                        'scale_x': 1.0,
                        'scale_y': 1.0,
                        'name': found_name,
                        'uuid': to_match if dc_info['prop_type'] == 'string' else str(to_match)
                    }
        finally:
            obs.obs_data_release(settings)
    finally:
        obs.obs_properties_destroy(props)
    
    return None


def release_sceneitem():
    """Release the current scene item and reset state."""
    global source, sceneitem, sceneitem_info_orig, sceneitem_crop_orig
    global crop_filter, crop_filter_temp, crop_filter_settings
    global is_timer_running
    
    if is_timer_running:
        obs.timer_remove(on_timer)
        is_timer_running = False
    
    if zoom_controller:
        zoom_controller.reset()
    
    if sceneitem is not None:
        # Remove crop filter
        if crop_filter is not None and source is not None:
            log("Removing zoom crop filter")
            obs.obs_source_filter_remove(source, crop_filter)
            obs.obs_source_release(crop_filter)
            crop_filter = None
        
        # Remove temp crop filter
        if crop_filter_temp is not None and source is not None:
            log("Removing temp crop filter")
            obs.obs_source_filter_remove(source, crop_filter_temp)
            obs.obs_source_release(crop_filter_temp)
            crop_filter_temp = None
        
        # Release crop filter settings
        if crop_filter_settings is not None:
            obs.obs_data_release(crop_filter_settings)
            crop_filter_settings = None
        
        # Restore original transform
        if sceneitem_info_orig is not None:
            log("Restoring original transform")
            obs.obs_sceneitem_set_info2(sceneitem, sceneitem_info_orig)
            sceneitem_info_orig = None
        
        # Restore original crop
        if sceneitem_crop_orig is not None:
            log("Restoring original crop")
            obs.obs_sceneitem_set_crop(sceneitem, sceneitem_crop_orig)
            sceneitem_crop_orig = None
        
        obs.obs_sceneitem_release(sceneitem)
        sceneitem = None
    
    if source is not None:
        obs.obs_source_release(source)
        source = None


def refresh_sceneitem(find_newest=False):
    """Refresh the scene item with updated source info."""
    global source, sceneitem, sceneitem_info_orig, sceneitem_crop_orig
    global crop_filter, crop_filter_settings
    
    if find_newest:
        release_sceneitem()
        
        if source_name == "" or source_name == "obs-zoom-to-mouse-none":
            return
        
        log(f"Finding scene item for '{source_name}'")
        
        source = obs.obs_get_source_by_name(source_name)
        if source is None:
            log(f"Source '{source_name}' not found")
            return
        
        # Get source dimensions
        source_width = obs.obs_source_get_width(source)
        source_height = obs.obs_source_get_height(source)
        
        # Find scene item in current scene
        scene_source = obs.obs_frontend_get_current_scene()
        if scene_source is not None:
            scene = obs.obs_scene_from_source(scene_source)
            sceneitem = obs.obs_scene_find_source_recursive(scene, source_name)
            
            if sceneitem is not None:
                log(f"Found scene item '{source_name}'")
                obs.obs_sceneitem_addref(sceneitem)
            
            obs.obs_source_release(scene_source)
        
        if sceneitem is None:
            log(f"Scene item '{source_name}' not in current scene")
            obs.obs_source_release(source)
            source = None
            return
    
    if sceneitem is None or source is None:
        return
    
    # Get monitor info
    monitor_info = get_monitor_info_from_source(source)
    
    # Get source dimensions
    source_width = obs.obs_source_get_width(source)
    source_height = obs.obs_source_get_height(source)
    
    if source_width == 0 or source_height == 0:
        source_width = obs.obs_source_get_base_width(source)
        source_height = obs.obs_source_get_base_height(source)
    
    log(f"Source size: {source_width}x{source_height}")
    
    # Auto-detect Retina scale on macOS
    scale_x = 1.0
    scale_y = 1.0
    display_x = 0
    display_y = 0
    
    if monitor_info:
        display_x = monitor_info.get('x', 0)
        display_y = monitor_info.get('y', 0)
        
        # Calculate scale from source vs display dimensions
        if monitor_info['width'] > 0 and monitor_info['height'] > 0:
            detected_scale_x = source_width / monitor_info['width']
            detected_scale_y = source_height / monitor_info['height']
            
            if 1.0 <= detected_scale_x <= 3.0 and 1.0 <= detected_scale_y <= 3.0:
                scale_x = round(detected_scale_x * 2) / 2
                scale_y = round(detected_scale_y * 2) / 2
                
                if scale_x != 1.0 or scale_y != 1.0:
                    log(f"Detected Retina scale: {scale_x}x{scale_y}")
    
    # Save original transform
    sceneitem_info_orig = obs.obs_transform_info()
    obs.obs_sceneitem_get_info2(sceneitem, sceneitem_info_orig)
    
    sceneitem_crop_orig = obs.obs_sceneitem_crop()
    obs.obs_sceneitem_get_crop(sceneitem, sceneitem_crop_orig)
    
    # Set up zoom controller with source info
    if zoom_controller:
        zoom_controller.set_source_info(
            width=source_width,
            height=source_height,
            crop_left=sceneitem_crop_orig.left,
            crop_top=sceneitem_crop_orig.top,
            crop_right=sceneitem_crop_orig.right,
            crop_bottom=sceneitem_crop_orig.bottom,
            scale_x=scale_x,
            scale_y=scale_y,
            display_x=display_x,
            display_y=display_y
        )
    
    # Get or create crop filter
    crop_filter = obs.obs_source_get_filter_by_name(source, CROP_FILTER_NAME)
    if crop_filter is None:
        crop_filter_settings = obs.obs_data_create()
        obs.obs_data_set_bool(crop_filter_settings, "relative", False)
        crop_filter = obs.obs_source_create_private("crop_filter", CROP_FILTER_NAME, crop_filter_settings)
        obs.obs_source_filter_add(source, crop_filter)
    else:
        crop_filter_settings = obs.obs_source_get_settings(crop_filter)
    
    # Move filter to bottom
    obs.obs_source_filter_set_order(source, crop_filter, obs.OBS_ORDER_MOVE_BOTTOM)
    
    # Set initial crop
    set_crop(0, 0, source_width, source_height)


def set_crop(x, y, width, height):
    """Set the crop filter values."""
    if crop_filter is None or crop_filter_settings is None:
        return
    
    if sceneitem is not None:
        obs.obs_sceneitem_defer_update_begin(sceneitem)
    
    obs.obs_data_set_int(crop_filter_settings, "left", int(x))
    obs.obs_data_set_int(crop_filter_settings, "top", int(y))
    obs.obs_data_set_int(crop_filter_settings, "cx", int(width))
    obs.obs_data_set_int(crop_filter_settings, "cy", int(height))
    obs.obs_source_update(crop_filter, crop_filter_settings)
    
    if sceneitem is not None:
        obs.obs_sceneitem_defer_update_end(sceneitem)


def on_crop_changed(crop):
    """Callback when zoom controller crop changes."""
    set_crop(crop.x, crop.y, crop.width, crop.height)


def on_toggle_zoom(pressed):
    """Hotkey callback for zoom toggle."""
    if pressed and zoom_controller and mouse_tracker:
        pos = mouse_tracker.position
        zoom_controller.toggle_zoom(pos[0], pos[1])
        
        # Start timer if needed
        global is_timer_running
        if not is_timer_running and zoom_controller.is_zoomed:
            is_timer_running = True
            timer_interval = int(obs.obs_get_frame_interval_ns() / 1000000)
            obs.timer_add(on_timer, max(timer_interval, 1))


def on_toggle_follow(pressed):
    """Hotkey callback for follow toggle."""
    if pressed and zoom_controller:
        zoom_controller.toggle_follow()
        log(f"Following: {zoom_controller.is_following}")
        
        # Start timer if following
        global is_timer_running
        if not is_timer_running and zoom_controller.is_following:
            is_timer_running = True
            timer_interval = int(obs.obs_get_frame_interval_ns() / 1000000)
            obs.timer_add(on_timer, max(timer_interval, 1))


def on_timer():
    """Timer callback for zoom updates."""
    global is_timer_running
    
    if zoom_controller is None or mouse_tracker is None:
        return
    
    # Get mouse position
    pos = mouse_tracker.position
    
    # Update zoom controller
    changed = zoom_controller.update(0.016, pos[0], pos[1])  # ~60fps
    
    # Stop timer if no longer needed
    if not zoom_controller.is_zoomed and not zoom_controller.is_animating:
        is_timer_running = False
        obs.timer_remove(on_timer)


def on_frontend_event(event):
    """Frontend event callback."""
    global is_obs_loaded
    
    if event == obs.OBS_FRONTEND_EVENT_SCENE_CHANGED:
        log("Scene changed")
        if is_obs_loaded:
            refresh_sceneitem(True)
    
    elif event == obs.OBS_FRONTEND_EVENT_FINISHED_LOADING:
        log("OBS finished loading")
        is_obs_loaded = True
        refresh_sceneitem(True)
    
    elif event == obs.OBS_FRONTEND_EVENT_SCRIPTING_SHUTDOWN:
        log("OBS shutting down")
        script_unload()


def on_transition_start(calldata):
    """Transition start callback."""
    log("Transition started")
    release_sceneitem()


# OBS Script Interface

def script_description():
    """Return script description."""
    return f"""<h3>Zoom to Mouse v{VERSION}</h3>
<p>Zoom a display capture source to focus on the mouse cursor.</p>
<p>Python Edition with enhanced features:</p>
<ul>
<li>Multiple zoom profiles</li>
<li>Advanced easing options</li>
<li>WebSocket remote control</li>
<li>Automatic Retina/HiDPI detection</li>
</ul>
<p><a href="https://github.com/BlankSourceCode/obs-zoom-to-mouse">GitHub</a></p>"""


def script_load(settings):
    """Called when script is loaded."""
    global mouse_tracker, display_manager, zoom_controller, config_manager
    global debug_logging, current_profile_name, is_obs_loaded
    
    log("Loading OBS Zoom to Mouse")
    
    # Initialize config manager
    config_manager = ConfigManager(script_path=__file__)
    config_manager.load()
    
    # Get debug setting
    debug_logging = config_manager.config.debug_logging
    
    # Initialize display manager
    display_manager = DisplayManager()
    display_manager.set_display_overrides(config_manager.config.display_overrides)
    
    # Initialize mouse tracker
    mouse_tracker = MouseTracker()
    mouse_tracker.start()
    
    # Initialize zoom controller with default profile
    current_profile_name = config_manager.config.default_profile
    profile = config_manager.get_profile(current_profile_name)
    zoom_controller = ZoomController(profile)
    zoom_controller.set_callbacks(on_crop_changed=on_crop_changed)
    
    # Register hotkeys
    obs.obs_hotkey_register_frontend("toggle_zoom_hotkey", "Toggle zoom to mouse", on_toggle_zoom)
    obs.obs_hotkey_register_frontend("toggle_follow_hotkey", "Toggle follow mouse", on_toggle_follow)
    
    # Load hotkey bindings
    hotkey_zoom_array = obs.obs_data_get_array(settings, "obs_zoom_to_mouse.hotkey.zoom")
    hotkey_follow_array = obs.obs_data_get_array(settings, "obs_zoom_to_mouse.hotkey.follow")
    # Note: Hotkey loading would be done here but requires hotkey IDs
    
    # Register frontend event callback
    obs.obs_frontend_add_event_callback(on_frontend_event)
    
    # Check if OBS is already loaded
    current_scene = obs.obs_frontend_get_current_scene()
    is_obs_loaded = current_scene is not None
    if current_scene:
        obs.obs_source_release(current_scene)
    
    # Register transition callbacks
    transitions = obs.obs_frontend_get_transitions()
    if transitions:
        for transition in transitions:
            handler = obs.obs_source_get_signal_handler(transition)
            obs.signal_handler_connect(handler, "transition_start", on_transition_start)
        obs.source_list_release(transitions)
    
    # Start WebSocket server if enabled
    if config_manager.config.websocket.enabled:
        start_websocket_server()
    
    log("Script loaded successfully")


def script_unload():
    """Called when script is unloaded."""
    global mouse_tracker, ws_server, is_timer_running
    
    log("Unloading OBS Zoom to Mouse")
    
    # Stop timer
    if is_timer_running:
        obs.timer_remove(on_timer)
        is_timer_running = False
    
    # Release scene item
    release_sceneitem()
    
    # Stop mouse tracker
    if mouse_tracker:
        mouse_tracker.stop()
        mouse_tracker = None
    
    # Stop WebSocket server
    if ws_server:
        ws_server.stop()
        ws_server = None
    
    # Remove transition callbacks
    try:
        transitions = obs.obs_frontend_get_transitions()
        if transitions:
            for transition in transitions:
                handler = obs.obs_source_get_signal_handler(transition)
                obs.signal_handler_disconnect(handler, "transition_start", on_transition_start)
            obs.source_list_release(transitions)
    except Exception:
        pass
    
    # Save config
    if config_manager:
        config_manager.save()
    
    log("Script unloaded")


def script_defaults(settings):
    """Set default settings."""
    obs.obs_data_set_default_double(settings, "zoom_factor", 2.0)
    obs.obs_data_set_default_double(settings, "zoom_speed", 0.06)
    obs.obs_data_set_default_bool(settings, "auto_follow", True)
    obs.obs_data_set_default_double(settings, "follow_speed", 0.25)
    obs.obs_data_set_default_int(settings, "follow_border", 8)
    obs.obs_data_set_default_string(settings, "easing", "ease_in_out")
    obs.obs_data_set_default_string(settings, "profile", "standard")
    obs.obs_data_set_default_bool(settings, "debug_logging", False)


def script_properties():
    """Create script properties UI."""
    props = obs.obs_properties_create()
    
    # Source selection
    source_list = obs.obs_properties_add_list(
        props, "source", "Zoom Source",
        obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING
    )
    populate_source_list(source_list)
    
    # Refresh button
    obs.obs_properties_add_button(props, "refresh", "Refresh Sources", on_refresh_sources)
    
    # Profile selection
    profile_list = obs.obs_properties_add_list(
        props, "profile", "Zoom Profile",
        obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING
    )
    if config_manager:
        for name in config_manager.list_profiles():
            obs.obs_property_list_add_string(profile_list, name, name)
    
    # Zoom settings
    obs.obs_properties_add_float(props, "zoom_factor", "Zoom Factor", 1.0, 5.0, 0.5)
    obs.obs_properties_add_float_slider(props, "zoom_speed", "Zoom Speed", 0.01, 1.0, 0.01)
    
    # Follow settings
    obs.obs_properties_add_bool(props, "auto_follow", "Auto Follow Mouse")
    obs.obs_properties_add_float_slider(props, "follow_speed", "Follow Speed", 0.01, 1.0, 0.01)
    obs.obs_properties_add_int_slider(props, "follow_border", "Follow Border %", 0, 50, 1)
    
    # Easing selection
    easing_list = obs.obs_properties_add_list(
        props, "easing", "Animation Easing",
        obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING
    )
    easings = ["linear", "ease_in_out", "ease_in", "ease_out", "elastic", "bounce"]
    for name in easings:
        obs.obs_property_list_add_string(easing_list, name, name)
    
    # Debug logging
    obs.obs_properties_add_bool(props, "debug_logging", "Enable Debug Logging")
    
    # Help button
    obs.obs_properties_add_button(props, "help", "Help / Documentation", on_show_help)
    
    return props


def populate_source_list(prop):
    """Populate source list with display capture sources."""
    obs.obs_property_list_clear(prop)
    obs.obs_property_list_add_string(prop, "<None>", "obs-zoom-to-mouse-none")
    
    sources = obs.obs_enum_sources()
    if sources:
        dc_info = get_display_capture_info()
        for source_obj in sources:
            source_type = obs.obs_source_get_id(source_obj)
            
            is_display = False
            if dc_info:
                if source_type == dc_info['source_id']:
                    is_display = True
                elif dc_info.get('source_id_fallback') and source_type == dc_info['source_id_fallback']:
                    is_display = True
                elif dc_info.get('source_id_legacy') and source_type == dc_info['source_id_legacy']:
                    is_display = True
            
            if is_display:
                name = obs.obs_source_get_name(source_obj)
                obs.obs_property_list_add_string(prop, name, name)
        
        obs.source_list_release(sources)


def on_refresh_sources(props, prop):
    """Refresh sources button callback."""
    source_list = obs.obs_properties_get(props, "source")
    populate_source_list(source_list)
    return True


def on_show_help(props, prop):
    """Show help button callback."""
    help_text = f"""
OBS Zoom to Mouse v{VERSION}
============================

This script zooms a display capture source to focus on the mouse cursor.

SETUP:
1. Select your display capture source from the dropdown
2. Set up hotkeys in OBS Settings -> Hotkeys:
   - "Toggle zoom to mouse" - Start/stop zoom
   - "Toggle follow mouse" - Enable/disable mouse tracking

PROFILES:
Edit config.json to create custom zoom profiles with different settings.

FEATURES:
- Automatic Retina/HiDPI display detection
- Multiple easing animations
- WebSocket remote control (enable in config.json)
- Multi-monitor support

For more info: https://github.com/BlankSourceCode/obs-zoom-to-mouse
"""
    obs.script_log(obs.LOG_INFO, help_text)
    return False


def script_update(settings):
    """Called when settings are updated."""
    global source_name, debug_logging, current_profile_name
    
    old_source = source_name
    source_name = obs.obs_data_get_string(settings, "source")
    
    # Update debug logging
    debug_logging = obs.obs_data_get_bool(settings, "debug_logging")
    
    # Update profile
    new_profile = obs.obs_data_get_string(settings, "profile")
    if new_profile and new_profile != current_profile_name:
        current_profile_name = new_profile
        if config_manager:
            config_manager.set_default_profile(new_profile)
        if zoom_controller:
            zoom_controller.profile = config_manager.get_profile(new_profile)
    
    # Update profile settings from UI
    if zoom_controller:
        zoom_controller.profile.zoom_factor = obs.obs_data_get_double(settings, "zoom_factor")
        zoom_controller.profile.zoom_speed = obs.obs_data_get_double(settings, "zoom_speed")
        zoom_controller.profile.auto_follow = obs.obs_data_get_bool(settings, "auto_follow")
        zoom_controller.profile.follow_speed = obs.obs_data_get_double(settings, "follow_speed")
        zoom_controller.profile.follow_border = obs.obs_data_get_int(settings, "follow_border")
        zoom_controller.profile.easing = obs.obs_data_get_string(settings, "easing")
    
    # Refresh if source changed
    if source_name != old_source and is_obs_loaded:
        refresh_sceneitem(True)


def script_save(settings):
    """Called when settings are saved."""
    # Save config
    if config_manager:
        config_manager.save()


def start_websocket_server():
    """Start the WebSocket server."""
    global ws_server
    
    if ws_server:
        ws_server.stop()
    
    port = config_manager.config.websocket.port if config_manager else 8765
    ws_server = WebSocketServer(port=port)
    
    ws_server.set_callbacks(
        on_toggle_zoom=lambda: on_toggle_zoom(True),
        on_toggle_follow=lambda: on_toggle_follow(True),
        on_set_profile=lambda p: set_profile(p),
        on_mouse_position=lambda x, y: mouse_tracker.set_override(x, y) if mouse_tracker else None
    )
    
    if ws_server.start():
        log(f"WebSocket server started on port {port}")
    else:
        log("Failed to start WebSocket server")


def set_profile(profile_name):
    """Set the active profile."""
    global current_profile_name
    
    if config_manager and profile_name in config_manager.list_profiles():
        current_profile_name = profile_name
        if zoom_controller:
            zoom_controller.profile = config_manager.get_profile(profile_name)
        log(f"Profile changed to: {profile_name}")

