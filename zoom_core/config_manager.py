"""
Config Manager Module
JSON-based configuration with profile support
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any
from pathlib import Path


@dataclass
class ZoomProfile:
    """Configuration profile for zoom behavior."""
    
    name: str = "default"
    zoom_factor: float = 2.0
    zoom_speed: float = 0.06
    follow_speed: float = 0.25
    follow_border: int = 8
    follow_safezone_sensitivity: int = 4
    easing: str = "ease_in_out"
    auto_follow: bool = True
    follow_outside_bounds: bool = False
    auto_lock_on_reverse: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], name: str = "default") -> 'ZoomProfile':
        """Create from dictionary."""
        return cls(
            name=name,
            zoom_factor=data.get('zoom_factor', 2.0),
            zoom_speed=data.get('zoom_speed', 0.06),
            follow_speed=data.get('follow_speed', 0.25),
            follow_border=data.get('follow_border', 8),
            follow_safezone_sensitivity=data.get('follow_safezone_sensitivity', 4),
            easing=data.get('easing', 'ease_in_out'),
            auto_follow=data.get('auto_follow', True),
            follow_outside_bounds=data.get('follow_outside_bounds', False),
            auto_lock_on_reverse=data.get('auto_lock_on_reverse', False)
        )


@dataclass
class WebSocketConfig:
    """WebSocket server configuration."""
    
    enabled: bool = False
    port: int = 8765
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketConfig':
        return cls(
            enabled=data.get('enabled', False),
            port=data.get('port', 8765)
        )


@dataclass
class Config:
    """Main configuration object."""
    
    version: str = "2.0.0"
    default_profile: str = "standard"
    profiles: Dict[str, ZoomProfile] = field(default_factory=dict)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    display_overrides: Dict[str, Dict] = field(default_factory=dict)
    debug_logging: bool = False
    
    def __post_init__(self):
        # Ensure at least a default profile exists
        if not self.profiles:
            self.profiles['standard'] = ZoomProfile(name='standard')
    
    def get_profile(self, name: Optional[str] = None) -> ZoomProfile:
        """Get a profile by name, or the default profile."""
        if name is None:
            name = self.default_profile
        
        if name in self.profiles:
            return self.profiles[name]
        
        # Return default if requested profile doesn't exist
        if self.default_profile in self.profiles:
            return self.profiles[self.default_profile]
        
        # Return first available profile
        if self.profiles:
            return list(self.profiles.values())[0]
        
        # Create and return default
        default = ZoomProfile(name='standard')
        self.profiles['standard'] = default
        return default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        profiles_dict = {}
        for name, profile in self.profiles.items():
            profile_data = profile.to_dict()
            del profile_data['name']  # Name is the key
            profiles_dict[name] = profile_data
        
        return {
            'version': self.version,
            'default_profile': self.default_profile,
            'profiles': profiles_dict,
            'websocket': self.websocket.to_dict(),
            'display_overrides': self.display_overrides,
            'debug_logging': self.debug_logging
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create from dictionary."""
        profiles = {}
        for name, profile_data in data.get('profiles', {}).items():
            profiles[name] = ZoomProfile.from_dict(profile_data, name)
        
        return cls(
            version=data.get('version', '2.0.0'),
            default_profile=data.get('default_profile', 'standard'),
            profiles=profiles,
            websocket=WebSocketConfig.from_dict(data.get('websocket', {})),
            display_overrides=data.get('display_overrides', {}),
            debug_logging=data.get('debug_logging', False)
        )


class ConfigManager:
    """
    Manages loading, saving, and accessing configuration.
    
    Configuration is stored in a JSON file that can be:
    - In the same directory as the script
    - In a user config directory
    - Specified explicitly
    """
    
    DEFAULT_FILENAME = "config.json"
    
    def __init__(self, config_path: Optional[str] = None, script_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Explicit path to config file
            script_path: Path to the script (for locating default config)
        """
        self._config: Optional[Config] = None
        self._config_path: Optional[Path] = None
        self._script_path = Path(script_path) if script_path else None
        
        if config_path:
            self._config_path = Path(config_path)
        elif script_path:
            self._config_path = Path(script_path).parent / self.DEFAULT_FILENAME
    
    def _find_config_path(self) -> Path:
        """Find the config file path."""
        if self._config_path:
            return self._config_path
        
        # Try script directory first
        if self._script_path:
            script_config = self._script_path.parent / self.DEFAULT_FILENAME
            if script_config.exists():
                return script_config
        
        # Try current directory
        cwd_config = Path.cwd() / self.DEFAULT_FILENAME
        if cwd_config.exists():
            return cwd_config
        
        # Default to script directory or current directory
        if self._script_path:
            return self._script_path.parent / self.DEFAULT_FILENAME
        return cwd_config
    
    def load(self) -> Config:
        """
        Load configuration from file.
        
        Returns:
            Config object (creates default if file doesn't exist)
        """
        config_path = self._find_config_path()
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = Config.from_dict(data)
                self._config_path = config_path
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config from {config_path}: {e}")
                self._config = self._create_default_config()
        else:
            self._config = self._create_default_config()
            self._config_path = config_path
            # Save default config
            self.save()
        
        return self._config
    
    def save(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if saved successfully
        """
        if self._config is None:
            return False
        
        config_path = self._config_path or self._find_config_path()
        
        try:
            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving config to {config_path}: {e}")
            return False
    
    def _create_default_config(self) -> Config:
        """Create default configuration."""
        return Config(
            profiles={
                'standard': ZoomProfile(
                    name='standard',
                    zoom_factor=2.0,
                    zoom_speed=0.06,
                    follow_speed=0.25,
                    follow_border=8,
                    easing='ease_in_out',
                    auto_follow=True
                ),
                'presentation': ZoomProfile(
                    name='presentation',
                    zoom_factor=3.0,
                    zoom_speed=0.1,
                    follow_speed=0.3,
                    follow_border=15,
                    easing='ease_in_out',
                    auto_follow=True
                ),
                'quick': ZoomProfile(
                    name='quick',
                    zoom_factor=2.5,
                    zoom_speed=0.15,
                    follow_speed=0.4,
                    follow_border=10,
                    easing='ease_out',
                    auto_follow=True,
                    follow_outside_bounds=True
                )
            }
        )
    
    @property
    def config(self) -> Config:
        """Get current configuration (loads if not already loaded)."""
        if self._config is None:
            self.load()
        return self._config
    
    @property
    def current_profile(self) -> ZoomProfile:
        """Get the current active profile."""
        return self.config.get_profile()
    
    def get_profile(self, name: str) -> ZoomProfile:
        """Get a specific profile by name."""
        return self.config.get_profile(name)
    
    def set_default_profile(self, name: str) -> bool:
        """
        Set the default profile.
        
        Args:
            name: Profile name to set as default
            
        Returns:
            True if profile exists and was set
        """
        if name in self.config.profiles:
            self.config.default_profile = name
            return True
        return False
    
    def add_profile(self, profile: ZoomProfile) -> None:
        """Add or update a profile."""
        self.config.profiles[profile.name] = profile
    
    def remove_profile(self, name: str) -> bool:
        """
        Remove a profile.
        
        Args:
            name: Profile name to remove
            
        Returns:
            True if removed, False if not found or is the only profile
        """
        if name in self.config.profiles and len(self.config.profiles) > 1:
            del self.config.profiles[name]
            # Update default if we removed it
            if self.config.default_profile == name:
                self.config.default_profile = list(self.config.profiles.keys())[0]
            return True
        return False
    
    def list_profiles(self) -> list:
        """Get list of profile names."""
        return list(self.config.profiles.keys())
    
    def update_display_override(self, display_id: str, scale_x: float = None, 
                                 scale_y: float = None, **kwargs) -> None:
        """
        Update display override settings.
        
        Args:
            display_id: Display ID or UUID
            scale_x: X scale factor
            scale_y: Y scale factor
            **kwargs: Additional override properties
        """
        if display_id not in self.config.display_overrides:
            self.config.display_overrides[display_id] = {}
        
        if scale_x is not None:
            self.config.display_overrides[display_id]['scale_x'] = scale_x
        if scale_y is not None:
            self.config.display_overrides[display_id]['scale_y'] = scale_y
        
        self.config.display_overrides[display_id].update(kwargs)

