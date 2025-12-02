"""
Display Manager Module
Multi-display detection and Retina/HiDPI scale handling
"""

import sys
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# Try to import screeninfo for display detection
try:
    from screeninfo import get_monitors, Monitor
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False


@dataclass
class DisplayInfo:
    """Information about a display/monitor."""
    
    # Display identifier (platform-specific)
    id: str = ""
    name: str = ""
    
    # Position (top-left corner in virtual screen coordinates)
    x: int = 0
    y: int = 0
    
    # Size in logical pixels (points on macOS)
    width: int = 0
    height: int = 0
    
    # Size in physical pixels (backing pixels on Retina)
    width_px: int = 0
    height_px: int = 0
    
    # Scale factors (for Retina/HiDPI displays)
    scale_x: float = 1.0
    scale_y: float = 1.0
    
    # Is this the primary display?
    is_primary: bool = False
    
    # UUID for macOS display identification
    uuid: str = ""
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within this display's bounds."""
        return (self.x <= x < self.x + self.width and 
                self.y <= y < self.y + self.height)
    
    def to_local(self, x: int, y: int) -> Tuple[int, int]:
        """Convert global coordinates to display-local coordinates."""
        return (x - self.x, y - self.y)
    
    def to_pixels(self, x: int, y: int) -> Tuple[int, int]:
        """Convert logical coordinates to physical pixel coordinates."""
        return (int(x * self.scale_x), int(y * self.scale_y))
    
    def __repr__(self):
        return (f"DisplayInfo(name='{self.name}', "
                f"pos=({self.x}, {self.y}), "
                f"size={self.width}x{self.height}, "
                f"scale={self.scale_x}x{self.scale_y})")


class DisplayManager:
    """
    Manages display detection and coordinate transformation.
    
    Handles:
    - Multi-monitor setups
    - Retina/HiDPI scaling
    - Coordinate transformation between logical and physical pixels
    """
    
    def __init__(self):
        self._displays: List[DisplayInfo] = []
        self._display_overrides: Dict[str, Dict] = {}
        self._cached = False
        
        # macOS-specific helpers
        self._appkit_available = False
        self._setup_platform_helpers()
    
    def _setup_platform_helpers(self):
        """Setup platform-specific helpers for better display info."""
        if sys.platform == 'darwin':
            try:
                from AppKit import NSScreen
                self._appkit_available = True
            except ImportError:
                pass
    
    def set_display_overrides(self, overrides: Dict[str, Dict]):
        """
        Set manual overrides for display properties.
        
        Args:
            overrides: Dict mapping display ID/UUID to override properties
                       e.g., {"uuid": {"scale_x": 2.0, "scale_y": 2.0}}
        """
        self._display_overrides = overrides
        self._cached = False
    
    def refresh(self):
        """Refresh display information."""
        self._cached = False
        self._displays = self._detect_displays()
        self._apply_overrides()
        self._cached = True
    
    def _detect_displays(self) -> List[DisplayInfo]:
        """Detect all connected displays."""
        displays = []
        
        if sys.platform == 'darwin':
            displays = self._detect_displays_macos()
        elif SCREENINFO_AVAILABLE:
            displays = self._detect_displays_screeninfo()
        else:
            # Fallback: assume single display
            displays = [DisplayInfo(
                id="0",
                name="Primary Display",
                x=0, y=0,
                width=1920, height=1080,
                width_px=1920, height_px=1080,
                scale_x=1.0, scale_y=1.0,
                is_primary=True
            )]
        
        return displays
    
    def _detect_displays_macos(self) -> List[DisplayInfo]:
        """Detect displays on macOS using AppKit for accurate Retina info."""
        displays = []
        
        if self._appkit_available:
            try:
                from AppKit import NSScreen
                from Quartz import CGDisplayCreateUUIDFromDisplayID, CFUUIDCreateString
                import CoreFoundation
                
                for i, screen in enumerate(NSScreen.screens()):
                    frame = screen.frame()
                    backing_scale = screen.backingScaleFactor()
                    
                    # Get display ID and UUID
                    device_desc = screen.deviceDescription()
                    screen_number = device_desc.get('NSScreenNumber', 0)
                    
                    # Try to get UUID
                    uuid_str = ""
                    try:
                        uuid_ref = CGDisplayCreateUUIDFromDisplayID(screen_number)
                        if uuid_ref:
                            uuid_str = str(CFUUIDCreateString(None, uuid_ref))
                    except Exception:
                        uuid_str = str(screen_number)
                    
                    # Get localized name
                    name = screen.localizedName() if hasattr(screen, 'localizedName') else f"Display {i+1}"
                    
                    display = DisplayInfo(
                        id=str(screen_number),
                        name=name,
                        x=int(frame.origin.x),
                        # macOS has inverted Y (0 at bottom)
                        y=int(frame.origin.y),
                        width=int(frame.size.width),
                        height=int(frame.size.height),
                        width_px=int(frame.size.width * backing_scale),
                        height_px=int(frame.size.height * backing_scale),
                        scale_x=backing_scale,
                        scale_y=backing_scale,
                        is_primary=(i == 0),
                        uuid=uuid_str
                    )
                    displays.append(display)
                
                return displays
            except Exception:
                pass
        
        # Fall back to screeninfo
        return self._detect_displays_screeninfo()
    
    def _detect_displays_screeninfo(self) -> List[DisplayInfo]:
        """Detect displays using screeninfo library."""
        displays = []
        
        if not SCREENINFO_AVAILABLE:
            return displays
        
        try:
            monitors = get_monitors()
            for i, mon in enumerate(monitors):
                display = DisplayInfo(
                    id=str(i),
                    name=mon.name or f"Display {i+1}",
                    x=mon.x,
                    y=mon.y,
                    width=mon.width,
                    height=mon.height,
                    width_px=mon.width,  # screeninfo doesn't provide pixel size
                    height_px=mon.height,
                    scale_x=1.0,
                    scale_y=1.0,
                    is_primary=mon.is_primary if hasattr(mon, 'is_primary') else (i == 0)
                )
                displays.append(display)
        except Exception:
            pass
        
        return displays
    
    def _apply_overrides(self):
        """Apply manual overrides to display info."""
        for display in self._displays:
            # Check by UUID first, then by ID
            override = self._display_overrides.get(display.uuid)
            if override is None:
                override = self._display_overrides.get(display.id)
            
            if override:
                if 'scale_x' in override:
                    display.scale_x = override['scale_x']
                if 'scale_y' in override:
                    display.scale_y = override['scale_y']
                if 'width_px' in override:
                    display.width_px = override['width_px']
                if 'height_px' in override:
                    display.height_px = override['height_px']
    
    @property
    def displays(self) -> List[DisplayInfo]:
        """Get list of all displays."""
        if not self._cached:
            self.refresh()
        return self._displays
    
    @property
    def primary_display(self) -> Optional[DisplayInfo]:
        """Get the primary display."""
        for display in self.displays:
            if display.is_primary:
                return display
        return self.displays[0] if self.displays else None
    
    def get_display_at_point(self, x: int, y: int) -> Optional[DisplayInfo]:
        """
        Get the display containing the given point.
        
        Args:
            x: X coordinate in logical screen space
            y: Y coordinate in logical screen space
            
        Returns:
            DisplayInfo for the display at that point, or None
        """
        for display in self.displays:
            if display.contains_point(x, y):
                return display
        return None
    
    def get_display_by_id(self, display_id: str) -> Optional[DisplayInfo]:
        """Get display by ID."""
        for display in self.displays:
            if display.id == display_id:
                return display
        return None
    
    def get_display_by_uuid(self, uuid: str) -> Optional[DisplayInfo]:
        """Get display by UUID (macOS)."""
        for display in self.displays:
            if display.uuid == uuid:
                return display
        return None
    
    def get_scale_for_source(self, source_width: int, source_height: int,
                              display: Optional[DisplayInfo] = None) -> Tuple[float, float]:
        """
        Calculate scale factors by comparing source size to display size.
        
        This is useful for automatically detecting Retina scaling by
        comparing OBS source dimensions (in pixels) to display dimensions
        (in points).
        
        Args:
            source_width: OBS source width in pixels
            source_height: OBS source height in pixels
            display: Display to compare against, or primary if None
            
        Returns:
            Tuple of (scale_x, scale_y)
        """
        if display is None:
            display = self.primary_display
        
        if display is None or display.width == 0 or display.height == 0:
            return (1.0, 1.0)
        
        scale_x = source_width / display.width
        scale_y = source_height / display.height
        
        # Round to nearest 0.5 to handle slight variations
        scale_x = round(scale_x * 2) / 2
        scale_y = round(scale_y * 2) / 2
        
        # Sanity check: scale should be between 1x and 3x
        if not (1.0 <= scale_x <= 3.0):
            scale_x = 1.0
        if not (1.0 <= scale_y <= 3.0):
            scale_y = 1.0
        
        return (scale_x, scale_y)
    
    def transform_mouse_to_source(self, mouse_x: int, mouse_y: int,
                                   display: Optional[DisplayInfo] = None,
                                   source_offset_x: int = 0,
                                   source_offset_y: int = 0) -> Tuple[int, int]:
        """
        Transform mouse coordinates to source coordinates.
        
        Handles:
        - Display offset (for multi-monitor)
        - Retina/HiDPI scaling
        - Source crop offset
        
        Args:
            mouse_x: Mouse X in screen coordinates
            mouse_y: Mouse Y in screen coordinates
            display: Display info, or detect from mouse position
            source_offset_x: Source crop X offset
            source_offset_y: Source crop Y offset
            
        Returns:
            Tuple of (x, y) in source pixel coordinates
        """
        if display is None:
            display = self.get_display_at_point(mouse_x, mouse_y)
        
        if display is None:
            display = self.primary_display
        
        if display is None:
            return (mouse_x - source_offset_x, mouse_y - source_offset_y)
        
        # Convert to display-local coordinates
        local_x = mouse_x - display.x
        local_y = mouse_y - display.y
        
        # Apply scaling (convert points to pixels)
        pixel_x = int(local_x * display.scale_x)
        pixel_y = int(local_y * display.scale_y)
        
        # Apply source offset
        source_x = pixel_x - source_offset_x
        source_y = pixel_y - source_offset_y
        
        return (source_x, source_y)


# Module-level convenience
_global_manager: Optional[DisplayManager] = None

def get_display_manager() -> DisplayManager:
    """Get or create global display manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = DisplayManager()
    return _global_manager

