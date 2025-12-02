"""
OBS Zoom to Mouse - Core Module
Cross-platform zoom functionality for OBS Studio
"""

from .mouse_tracker import MouseTracker
from .display_manager import DisplayManager, DisplayInfo
from .zoom_controller import ZoomController, ZoomState, CropRect
from .config_manager import ConfigManager, ZoomProfile, Config
from .easing import EASING_FUNCTIONS, lerp, get_easing, clamp
from .visual_overlay import ZoomOverlay, OverlayConfig, SimpleStateIndicator

__all__ = [
    # Mouse tracking
    'MouseTracker',
    
    # Display management
    'DisplayManager',
    'DisplayInfo',
    
    # Zoom control
    'ZoomController',
    'ZoomState',
    'CropRect',
    
    # Configuration
    'ConfigManager',
    'ZoomProfile',
    'Config',
    
    # Easing/Animation
    'EASING_FUNCTIONS',
    'lerp',
    'get_easing',
    'clamp',
    
    # Visual overlay
    'ZoomOverlay',
    'OverlayConfig',
    'SimpleStateIndicator',
]

__version__ = '2.0.0'

