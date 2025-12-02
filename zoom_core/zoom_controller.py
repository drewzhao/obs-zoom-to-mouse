"""
Zoom Controller Module
State machine for managing zoom behavior and animations
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Tuple, Optional, Callable, Any
import math

from .easing import get_easing, lerp, clamp
from .config_manager import ZoomProfile


class ZoomState(Enum):
    """States of the zoom state machine."""
    IDLE = auto()          # Not zoomed
    ZOOMING_IN = auto()    # Animating zoom in
    ZOOMED = auto()        # Zoomed and stationary
    FOLLOWING = auto()     # Zoomed and following mouse
    ZOOMING_OUT = auto()   # Animating zoom out


@dataclass
class CropRect:
    """Rectangle for crop/zoom region."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    
    def copy(self) -> 'CropRect':
        return CropRect(self.x, self.y, self.width, self.height)
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)
    
    def to_int_tuple(self) -> Tuple[int, int, int, int]:
        return (int(self.x), int(self.y), int(self.width), int(self.height))


@dataclass
class SourceInfo:
    """Information about the zoom source."""
    width: int = 0
    height: int = 0
    # Existing crop from transform or filters
    crop_left: int = 0
    crop_top: int = 0
    crop_right: int = 0
    crop_bottom: int = 0
    # Scale factors for coordinate transformation
    scale_x: float = 1.0
    scale_y: float = 1.0
    # Display offset (for multi-monitor)
    display_x: int = 0
    display_y: int = 0


class ZoomController:
    """
    Controls zoom state and animations.
    
    Manages the state machine for zooming, following, and animations.
    Does not directly interact with OBS - instead provides crop rectangles
    that the main script applies to OBS.
    """
    
    def __init__(self, profile: Optional[ZoomProfile] = None):
        """
        Initialize zoom controller.
        
        Args:
            profile: Zoom profile with settings
        """
        self._profile = profile or ZoomProfile()
        self._state = ZoomState.IDLE
        
        # Source information
        self._source_info = SourceInfo()
        
        # Current and target crop rectangles
        self._crop_current = CropRect()
        self._crop_target = CropRect()
        self._crop_original = CropRect()
        
        # Animation progress (0-1)
        self._animation_progress = 0.0
        
        # Following state
        self._is_following = False
        self._locked_center: Optional[Tuple[float, float]] = None
        self._locked_last_pos: Optional[Tuple[float, float]] = None
        self._locked_last_diff: Optional[Tuple[float, float]] = None
        
        # Callbacks
        self._on_crop_changed: Optional[Callable[[CropRect], None]] = None
        self._on_state_changed: Optional[Callable[[ZoomState], None]] = None
    
    @property
    def state(self) -> ZoomState:
        """Current zoom state."""
        return self._state
    
    @property
    def profile(self) -> ZoomProfile:
        """Current zoom profile."""
        return self._profile
    
    @profile.setter
    def profile(self, value: ZoomProfile):
        """Set zoom profile."""
        self._profile = value
    
    @property
    def is_zoomed(self) -> bool:
        """Check if currently zoomed (any non-IDLE state)."""
        return self._state != ZoomState.IDLE
    
    @property
    def is_animating(self) -> bool:
        """Check if currently animating."""
        return self._state in (ZoomState.ZOOMING_IN, ZoomState.ZOOMING_OUT)
    
    @property
    def is_following(self) -> bool:
        """Check if following mouse."""
        return self._is_following and self._state in (ZoomState.ZOOMED, ZoomState.FOLLOWING)
    
    @property
    def current_crop(self) -> CropRect:
        """Get current crop rectangle."""
        return self._crop_current
    
    def set_source_info(self, width: int, height: int,
                        crop_left: int = 0, crop_top: int = 0,
                        crop_right: int = 0, crop_bottom: int = 0,
                        scale_x: float = 1.0, scale_y: float = 1.0,
                        display_x: int = 0, display_y: int = 0):
        """
        Set source information.
        
        Args:
            width: Source width in pixels
            height: Source height in pixels
            crop_left/top/right/bottom: Existing crop values
            scale_x/y: Scale factors for coordinate transformation
            display_x/y: Display offset for multi-monitor
        """
        self._source_info = SourceInfo(
            width=width,
            height=height,
            crop_left=crop_left,
            crop_top=crop_top,
            crop_right=crop_right,
            crop_bottom=crop_bottom,
            scale_x=scale_x,
            scale_y=scale_y,
            display_x=display_x,
            display_y=display_y
        )
        
        # Set original crop to full source
        self._crop_original = CropRect(0, 0, float(width), float(height))
        self._crop_current = self._crop_original.copy()
    
    def set_callbacks(self, 
                      on_crop_changed: Optional[Callable[[CropRect], None]] = None,
                      on_state_changed: Optional[Callable[[ZoomState], None]] = None):
        """
        Set callbacks for state changes.
        
        Args:
            on_crop_changed: Called when crop rectangle changes
            on_state_changed: Called when state changes
        """
        self._on_crop_changed = on_crop_changed
        self._on_state_changed = on_state_changed
    
    def _set_state(self, new_state: ZoomState):
        """Change state and notify callback."""
        if new_state != self._state:
            self._state = new_state
            if self._on_state_changed:
                self._on_state_changed(new_state)
    
    def _notify_crop_changed(self):
        """Notify crop changed callback."""
        if self._on_crop_changed:
            self._on_crop_changed(self._crop_current)
    
    def _transform_mouse(self, mouse_x: int, mouse_y: int) -> Tuple[float, float]:
        """
        Transform mouse coordinates to source coordinates.
        
        Args:
            mouse_x: Mouse X in screen coordinates
            mouse_y: Mouse Y in screen coordinates
            
        Returns:
            Tuple of (x, y) in source coordinates
        """
        # Apply display offset
        x = mouse_x - self._source_info.display_x
        y = mouse_y - self._source_info.display_y
        
        # Apply scale (for Retina/HiDPI)
        x *= self._source_info.scale_x
        y *= self._source_info.scale_y
        
        # Apply crop offset
        x -= self._source_info.crop_left
        y -= self._source_info.crop_top
        
        return (float(x), float(y))
    
    def _calculate_target_crop(self, mouse_x: int, mouse_y: int) -> CropRect:
        """
        Calculate target crop rectangle centered on mouse.
        
        Args:
            mouse_x: Mouse X in screen coordinates
            mouse_y: Mouse Y in screen coordinates
            
        Returns:
            Target crop rectangle
        """
        # Transform mouse to source coordinates
        source_x, source_y = self._transform_mouse(mouse_x, mouse_y)
        
        # Calculate zoomed size
        zoom = self._profile.zoom_factor
        new_width = self._source_info.width / zoom
        new_height = self._source_info.height / zoom
        
        # Center on mouse
        target_x = source_x - new_width / 2
        target_y = source_y - new_height / 2
        
        # Clamp to source bounds
        max_x = self._source_info.width - new_width
        max_y = self._source_info.height - new_height
        target_x = clamp(target_x, 0, max_x)
        target_y = clamp(target_y, 0, max_y)
        
        return CropRect(target_x, target_y, new_width, new_height)
    
    def toggle_zoom(self, mouse_x: int = 0, mouse_y: int = 0):
        """
        Toggle zoom state.
        
        Args:
            mouse_x: Current mouse X position
            mouse_y: Current mouse Y position
        """
        if self._state == ZoomState.IDLE:
            # Start zooming in
            self._crop_target = self._calculate_target_crop(mouse_x, mouse_y)
            self._animation_progress = 0.0
            self._set_state(ZoomState.ZOOMING_IN)
            self._locked_center = None
            self._locked_last_pos = None
            
        elif self._state in (ZoomState.ZOOMED, ZoomState.FOLLOWING):
            # Start zooming out
            self._crop_target = self._crop_original.copy()
            self._animation_progress = 0.0
            self._set_state(ZoomState.ZOOMING_OUT)
            self._is_following = False
            self._locked_center = None
    
    def toggle_follow(self):
        """Toggle mouse following."""
        if self._state in (ZoomState.ZOOMED, ZoomState.FOLLOWING):
            self._is_following = not self._is_following
            if self._is_following:
                self._set_state(ZoomState.FOLLOWING)
            else:
                self._set_state(ZoomState.ZOOMED)
    
    def update(self, dt: float, mouse_x: int, mouse_y: int) -> bool:
        """
        Update zoom state and animations.
        
        Args:
            dt: Time delta since last update (seconds)
            mouse_x: Current mouse X position
            mouse_y: Current mouse Y position
            
        Returns:
            True if crop changed and needs to be applied
        """
        if self._state == ZoomState.IDLE:
            return False
        
        changed = False
        
        if self._state == ZoomState.ZOOMING_IN:
            changed = self._update_zoom_in(dt, mouse_x, mouse_y)
        elif self._state == ZoomState.ZOOMING_OUT:
            changed = self._update_zoom_out(dt)
        elif self._state in (ZoomState.ZOOMED, ZoomState.FOLLOWING):
            changed = self._update_following(dt, mouse_x, mouse_y)
        
        if changed:
            self._notify_crop_changed()
        
        return changed
    
    def _update_zoom_in(self, dt: float, mouse_x: int, mouse_y: int) -> bool:
        """Update zoom-in animation."""
        self._animation_progress += self._profile.zoom_speed
        
        if self._animation_progress >= 1.0:
            self._animation_progress = 1.0
            self._crop_current = self._crop_target.copy()
            
            # Transition to zoomed state
            if self._profile.auto_follow:
                self._is_following = True
                self._set_state(ZoomState.FOLLOWING)
                # Set initial locked center
                self._locked_center = (
                    self._crop_current.x + self._crop_current.width / 2,
                    self._crop_current.y + self._crop_current.height / 2
                )
            else:
                self._set_state(ZoomState.ZOOMED)
            
            return True
        
        # Update target if auto-follow is on (track mouse during zoom animation)
        if self._profile.auto_follow:
            self._crop_target = self._calculate_target_crop(mouse_x, mouse_y)
        
        # Interpolate current crop
        easing = get_easing(self._profile.easing)
        t = easing(self._animation_progress)
        
        self._crop_current.x = lerp(self._crop_original.x, self._crop_target.x, t)
        self._crop_current.y = lerp(self._crop_original.y, self._crop_target.y, t)
        self._crop_current.width = lerp(self._crop_original.width, self._crop_target.width, t)
        self._crop_current.height = lerp(self._crop_original.height, self._crop_target.height, t)
        
        return True
    
    def _update_zoom_out(self, dt: float) -> bool:
        """Update zoom-out animation."""
        self._animation_progress += self._profile.zoom_speed
        
        if self._animation_progress >= 1.0:
            self._animation_progress = 1.0
            self._crop_current = self._crop_original.copy()
            self._set_state(ZoomState.IDLE)
            return True
        
        # Interpolate current crop
        easing = get_easing(self._profile.easing)
        t = easing(self._animation_progress)
        
        # Store starting position for interpolation
        start_x = self._crop_current.x if self._animation_progress == self._profile.zoom_speed else lerp(
            self._crop_target.x, self._crop_original.x, easing(self._animation_progress - self._profile.zoom_speed)
        )
        
        self._crop_current.x = lerp(self._crop_target.x, self._crop_original.x, t)
        self._crop_current.y = lerp(self._crop_target.y, self._crop_original.y, t)
        self._crop_current.width = lerp(self._crop_target.width, self._crop_original.width, t)
        self._crop_current.height = lerp(self._crop_target.height, self._crop_original.height, t)
        
        return True
    
    def _update_following(self, dt: float, mouse_x: int, mouse_y: int) -> bool:
        """Update mouse following."""
        if not self._is_following:
            return False
        
        # Calculate target position
        target = self._calculate_target_crop(mouse_x, mouse_y)
        source_x, source_y = self._transform_mouse(mouse_x, mouse_y)
        
        # Check if mouse is within bounds
        if not self._profile.follow_outside_bounds:
            if (source_x < target.x or source_x > target.x + target.width or
                source_y < target.y or source_y > target.y + target.height):
                return False
        
        # Handle locked center (safe zone)
        if self._locked_center is not None:
            diff_x = source_x - self._locked_center[0]
            diff_y = source_y - self._locked_center[1]
            
            # Calculate border distance
            border_x = target.width * (0.5 - self._profile.follow_border * 0.01)
            border_y = target.height * (0.5 - self._profile.follow_border * 0.01)
            
            # Check if mouse moved outside safe zone
            if abs(diff_x) > border_x or abs(diff_y) > border_y:
                self._locked_center = None
                self._locked_last_pos = (source_x, source_y)
                self._locked_last_diff = (diff_x, diff_y)
        
        if self._locked_center is not None:
            return False
        
        # Interpolate towards target
        speed = self._profile.follow_speed
        changed = False
        
        if abs(target.x - self._crop_current.x) > 0.5 or abs(target.y - self._crop_current.y) > 0.5:
            self._crop_current.x = lerp(self._crop_current.x, target.x, speed)
            self._crop_current.y = lerp(self._crop_current.y, target.y, speed)
            changed = True
        
        # Check for auto-lock
        if self._locked_last_pos is not None:
            sensitivity = self._profile.follow_safezone_sensitivity
            diff_x = abs(self._crop_current.x - target.x)
            diff_y = abs(self._crop_current.y - target.y)
            
            # Check for direction reversal (auto-lock)
            should_lock = False
            if self._profile.auto_lock_on_reverse and self._locked_last_diff:
                auto_diff_x = source_x - self._locked_last_pos[0]
                auto_diff_y = source_y - self._locked_last_pos[1]
                
                if abs(self._locked_last_diff[0]) > abs(self._locked_last_diff[1]):
                    if (auto_diff_x < 0 and self._locked_last_diff[0] > 0) or \
                       (auto_diff_x > 0 and self._locked_last_diff[0] < 0):
                        should_lock = True
                else:
                    if (auto_diff_y < 0 and self._locked_last_diff[1] > 0) or \
                       (auto_diff_y > 0 and self._locked_last_diff[1] < 0):
                        should_lock = True
            
            # Lock if close enough or direction reversed
            if should_lock or (diff_x <= sensitivity and diff_y <= sensitivity):
                self._locked_center = (
                    self._crop_current.x + self._crop_current.width / 2,
                    self._crop_current.y + self._crop_current.height / 2
                )
                self._locked_last_pos = None
        
        if self._locked_last_pos is not None:
            self._locked_last_pos = (source_x, source_y)
        
        return changed
    
    def reset(self):
        """Reset to idle state."""
        self._state = ZoomState.IDLE
        self._crop_current = self._crop_original.copy()
        self._animation_progress = 0.0
        self._is_following = False
        self._locked_center = None
        self._locked_last_pos = None
        self._notify_crop_changed()
    
    def get_state_info(self) -> dict:
        """Get current state information for debugging/status."""
        return {
            'state': self._state.name,
            'is_following': self._is_following,
            'animation_progress': self._animation_progress,
            'crop': self._crop_current.to_tuple(),
            'zoom_factor': self._profile.zoom_factor,
            'locked': self._locked_center is not None
        }

