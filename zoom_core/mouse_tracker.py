"""
Mouse Tracker Module
Cross-platform mouse position tracking using pynput
"""

import sys
import threading
from typing import Tuple, Optional, Callable

# Try to import pynput, fall back to platform-specific methods if not available
try:
    from pynput import mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class MouseTracker:
    """
    Cross-platform mouse position tracker.
    
    Uses pynput for reliable cross-platform mouse tracking.
    Falls back to platform-specific methods if pynput is not available.
    """
    
    def __init__(self):
        self._position: Tuple[int, int] = (0, 0)
        self._lock = threading.Lock()
        self._listener: Optional[mouse.Listener] = None
        self._running = False
        self._override_position: Optional[Tuple[int, int]] = None
        self._on_move_callback: Optional[Callable[[int, int], None]] = None
        
        # Platform-specific fallback
        self._fallback_method: Optional[Callable[[], Tuple[int, int]]] = None
        if not PYNPUT_AVAILABLE:
            self._setup_fallback()
    
    def _setup_fallback(self):
        """Setup platform-specific fallback for mouse position."""
        if sys.platform == 'darwin':
            try:
                from Quartz import CGEventGetLocation, CGEventCreate
                def get_mouse_pos():
                    event = CGEventCreate(None)
                    point = CGEventGetLocation(event)
                    return (int(point.x), int(point.y))
                self._fallback_method = get_mouse_pos
            except ImportError:
                pass
        elif sys.platform == 'win32':
            try:
                import ctypes
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                def get_mouse_pos():
                    pt = POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    return (pt.x, pt.y)
                self._fallback_method = get_mouse_pos
            except Exception:
                pass
        elif sys.platform.startswith('linux'):
            try:
                from Xlib import display
                d = display.Display()
                root = d.screen().root
                def get_mouse_pos():
                    data = root.query_pointer()
                    return (data.root_x, data.root_y)
                self._fallback_method = get_mouse_pos
            except ImportError:
                pass
    
    def _on_move(self, x: int, y: int):
        """Callback when mouse moves."""
        with self._lock:
            self._position = (int(x), int(y))
        
        if self._on_move_callback:
            self._on_move_callback(int(x), int(y))
    
    @property
    def position(self) -> Tuple[int, int]:
        """
        Get current mouse position.
        
        Returns:
            Tuple of (x, y) coordinates in screen pixels.
            On macOS, these are in points (logical pixels).
        """
        # Check for override first (from WebSocket remote control)
        if self._override_position is not None:
            return self._override_position
        
        # If using pynput listener
        if self._listener and self._running:
            with self._lock:
                return self._position
        
        # Fallback method
        if self._fallback_method:
            return self._fallback_method()
        
        with self._lock:
            return self._position
    
    @property
    def x(self) -> int:
        """Get current mouse X coordinate."""
        return self.position[0]
    
    @property
    def y(self) -> int:
        """Get current mouse Y coordinate."""
        return self.position[1]
    
    def set_override(self, x: Optional[int], y: Optional[int]):
        """
        Set an override position (for remote control).
        
        Args:
            x: X coordinate, or None to clear override
            y: Y coordinate, or None to clear override
        """
        if x is None or y is None:
            self._override_position = None
        else:
            self._override_position = (x, y)
    
    def clear_override(self):
        """Clear any position override."""
        self._override_position = None
    
    def set_move_callback(self, callback: Optional[Callable[[int, int], None]]):
        """
        Set a callback to be called on mouse movement.
        
        Args:
            callback: Function taking (x, y) parameters, or None to clear
        """
        self._on_move_callback = callback
    
    def start(self):
        """Start tracking mouse position."""
        if self._running:
            return
        
        if PYNPUT_AVAILABLE:
            self._listener = mouse.Listener(on_move=self._on_move)
            self._listener.start()
            self._running = True
        elif self._fallback_method:
            self._running = True
    
    def stop(self):
        """Stop tracking mouse position."""
        if not self._running:
            return
        
        self._running = False
        
        if self._listener:
            self._listener.stop()
            self._listener = None
    
    def is_running(self) -> bool:
        """Check if tracker is running."""
        return self._running
    
    def poll(self) -> Tuple[int, int]:
        """
        Poll for current mouse position.
        
        This method actively queries the mouse position rather than
        using the cached value from the listener. Useful when the
        listener might not have started yet.
        
        Returns:
            Tuple of (x, y) coordinates
        """
        if self._override_position is not None:
            return self._override_position
        
        if self._fallback_method:
            pos = self._fallback_method()
            with self._lock:
                self._position = pos
            return pos
        
        # If pynput is available but we want to poll directly
        if PYNPUT_AVAILABLE:
            try:
                controller = mouse.Controller()
                pos = controller.position
                with self._lock:
                    self._position = (int(pos[0]), int(pos[1]))
                return self._position
            except Exception:
                pass
        
        with self._lock:
            return self._position


# Module-level convenience functions
_global_tracker: Optional[MouseTracker] = None

def get_mouse_position() -> Tuple[int, int]:
    """
    Get current mouse position using global tracker.
    
    Returns:
        Tuple of (x, y) coordinates
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MouseTracker()
        _global_tracker.start()
    return _global_tracker.position

def cleanup_global_tracker():
    """Clean up global mouse tracker."""
    global _global_tracker
    if _global_tracker is not None:
        _global_tracker.stop()
        _global_tracker = None

