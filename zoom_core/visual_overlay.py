"""
Visual Overlay Module
Provides visual feedback for zoom state using OBS text sources.

Note: Since Python scripts cannot use render callbacks in OBS,
this module creates/manages a text source that displays zoom status.
"""

from typing import Optional, Callable
from dataclasses import dataclass

# Try to import OBS - will be None outside of OBS environment
try:
    import obspython as obs
    OBS_AVAILABLE = True
except ImportError:
    obs = None
    OBS_AVAILABLE = False


@dataclass
class OverlayConfig:
    """Configuration for the visual overlay."""
    
    # Enable/disable overlay
    enabled: bool = False
    
    # Text source name
    source_name: str = "Zoom Indicator"
    
    # Display settings
    show_zoom_level: bool = True
    show_state: bool = True
    show_position: bool = False
    
    # Appearance
    font_size: int = 24
    font_face: str = "Arial"
    text_color: int = 0xFFFFFFFF  # ABGR format
    background_color: int = 0x80000000  # Semi-transparent black
    
    # Position (relative to canvas)
    position_x: int = 10
    position_y: int = 10
    
    # Auto-hide
    auto_hide: bool = True
    hide_delay_ms: int = 2000


class ZoomOverlay:
    """
    Manages a visual overlay showing zoom status.
    
    Creates a text source in OBS that displays:
    - Current zoom state (Zoomed/Following/Idle)
    - Zoom level
    - Optional position information
    
    The overlay automatically shows when zooming and hides after a delay.
    """
    
    def __init__(self, config: Optional[OverlayConfig] = None):
        """
        Initialize zoom overlay.
        
        Args:
            config: Overlay configuration
        """
        self._config = config or OverlayConfig()
        self._source: Optional[object] = None
        self._sceneitem: Optional[object] = None
        self._visible = False
        self._hide_timer_active = False
        
        # Current state
        self._zoom_level = 1.0
        self._state = "Idle"
        self._position = (0, 0)
    
    @property
    def config(self) -> OverlayConfig:
        """Get overlay configuration."""
        return self._config
    
    @config.setter
    def config(self, value: OverlayConfig):
        """Set overlay configuration."""
        self._config = value
        self._update_source_settings()
    
    def create_source(self) -> bool:
        """
        Create the overlay text source in OBS.
        
        Returns:
            True if source created successfully
        """
        if not OBS_AVAILABLE or not obs:
            return False
        
        if not self._config.enabled:
            return False
        
        # Check if source already exists
        existing = obs.obs_get_source_by_name(self._config.source_name)
        if existing:
            self._source = existing
            return True
        
        # Create text source settings
        settings = obs.obs_data_create()
        
        try:
            # Configure text source
            obs.obs_data_set_string(settings, "text", self._format_text())
            obs.obs_data_set_string(settings, "font", self._get_font_settings())
            
            # Create the source
            # Note: Source type varies by platform
            # - Windows: text_gdiplus_v2
            # - macOS: text_ft2_source_v2
            # - Linux: text_ft2_source_v2
            import sys
            if sys.platform == 'win32':
                source_type = "text_gdiplus_v2"
            else:
                source_type = "text_ft2_source_v2"
            
            self._source = obs.obs_source_create(
                source_type,
                self._config.source_name,
                settings,
                None
            )
            
            if self._source:
                # Source is private, won't show in sources list
                return True
            
        finally:
            obs.obs_data_release(settings)
        
        return False
    
    def destroy_source(self):
        """Destroy the overlay source."""
        if self._source:
            obs.obs_source_release(self._source)
            self._source = None
        
        self._sceneitem = None
    
    def add_to_scene(self, scene) -> bool:
        """
        Add overlay to a scene.
        
        Args:
            scene: OBS scene to add to
            
        Returns:
            True if added successfully
        """
        if not OBS_AVAILABLE or not obs or not self._source:
            return False
        
        # Check if already in scene
        self._sceneitem = obs.obs_scene_find_source(scene, self._config.source_name)
        if self._sceneitem:
            return True
        
        # Add to scene
        self._sceneitem = obs.obs_scene_add(scene, self._source)
        if self._sceneitem:
            # Position the overlay
            pos = obs.vec2()
            pos.x = self._config.position_x
            pos.y = self._config.position_y
            obs.obs_sceneitem_set_pos(self._sceneitem, pos)
            
            # Initially hidden
            obs.obs_sceneitem_set_visible(self._sceneitem, False)
            self._visible = False
            
            return True
        
        return False
    
    def show(self):
        """Show the overlay."""
        if not self._config.enabled:
            return
        
        self._visible = True
        
        if self._sceneitem and OBS_AVAILABLE:
            obs.obs_sceneitem_set_visible(self._sceneitem, True)
        
        # Start auto-hide timer if enabled
        if self._config.auto_hide:
            self._start_hide_timer()
    
    def hide(self):
        """Hide the overlay."""
        self._visible = False
        
        if self._sceneitem and OBS_AVAILABLE:
            obs.obs_sceneitem_set_visible(self._sceneitem, False)
    
    def update(self, zoom_level: float, state: str, position: tuple = (0, 0)):
        """
        Update overlay with current zoom information.
        
        Args:
            zoom_level: Current zoom factor
            state: Current state string ("Idle", "Zooming In", "Zoomed", "Following", "Zooming Out")
            position: Current zoom position (x, y)
        """
        self._zoom_level = zoom_level
        self._state = state
        self._position = position
        
        self._update_text()
        
        # Show overlay if zooming
        if state != "Idle" and self._config.enabled:
            self.show()
        elif state == "Idle" and self._visible and self._config.auto_hide:
            # Hide after delay when returning to idle
            self._start_hide_timer()
    
    def _format_text(self) -> str:
        """Format the overlay text."""
        parts = []
        
        if self._config.show_state:
            parts.append(self._state)
        
        if self._config.show_zoom_level and self._zoom_level != 1.0:
            parts.append(f"{self._zoom_level:.1f}x")
        
        if self._config.show_position and self._state != "Idle":
            parts.append(f"({int(self._position[0])}, {int(self._position[1])})")
        
        return " | ".join(parts) if parts else ""
    
    def _get_font_settings(self) -> str:
        """Get font settings string."""
        # Font settings format varies by source type
        return f'{{"face":"{self._config.font_face}","size":{self._config.font_size}}}'
    
    def _update_text(self):
        """Update the source text."""
        if not self._source or not OBS_AVAILABLE:
            return
        
        settings = obs.obs_source_get_settings(self._source)
        if settings:
            obs.obs_data_set_string(settings, "text", self._format_text())
            obs.obs_source_update(self._source, settings)
            obs.obs_data_release(settings)
    
    def _update_source_settings(self):
        """Update all source settings from config."""
        if not self._source or not OBS_AVAILABLE:
            return
        
        settings = obs.obs_source_get_settings(self._source)
        if settings:
            obs.obs_data_set_string(settings, "text", self._format_text())
            obs.obs_data_set_string(settings, "font", self._get_font_settings())
            obs.obs_source_update(self._source, settings)
            obs.obs_data_release(settings)
    
    def _start_hide_timer(self):
        """Start the auto-hide timer."""
        if not OBS_AVAILABLE:
            return
        
        # Cancel existing timer
        if self._hide_timer_active:
            obs.timer_remove(self._on_hide_timer)
        
        self._hide_timer_active = True
        obs.timer_add(self._on_hide_timer, self._config.hide_delay_ms)
    
    def _on_hide_timer(self):
        """Hide timer callback."""
        self._hide_timer_active = False
        obs.timer_remove(self._on_hide_timer)
        
        # Only hide if still in idle state
        if self._state == "Idle":
            self.hide()


# Simplified state indicator that just logs/prints (no OBS source required)
class SimpleStateIndicator:
    """
    Simple state indicator that doesn't require OBS sources.
    
    This can be used for debugging or when visual overlay is not available.
    Outputs state changes to the console/log.
    """
    
    def __init__(self, log_func: Optional[Callable[[str], None]] = None):
        """
        Initialize simple indicator.
        
        Args:
            log_func: Function to call for logging (defaults to print)
        """
        self._log = log_func or print
        self._last_state = ""
    
    def update(self, zoom_level: float, state: str, position: tuple = (0, 0)):
        """
        Update indicator with current state.
        
        Only logs when state changes to reduce noise.
        """
        state_str = f"{state} ({zoom_level:.1f}x)"
        
        if state_str != self._last_state:
            self._last_state = state_str
            if state != "Idle":
                self._log(f"Zoom: {state_str} at {position}")

