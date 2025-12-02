# OBS Zoom to Mouse - Python Edition

A powerful OBS Studio script that zooms your display capture source to focus on the mouse cursor.

**Version 2.0.0** - Complete Python rewrite with enhanced features.

## Features

### Core Features
- **Zoom to Mouse**: Click a hotkey to zoom in on your mouse position
- **Follow Mouse**: Automatically track the mouse while zoomed
- **Smooth Animations**: Multiple easing functions for professional transitions
- **Multi-Monitor Support**: Works with multiple displays

### New in Python Edition
- **Native Mouse Tracking**: Uses `pynput` for reliable cross-platform mouse tracking (no FFI required)
- **Automatic Retina/HiDPI Detection**: Correctly handles high-DPI displays on macOS and Windows
- **Zoom Profiles**: Save and switch between different zoom configurations
- **WebSocket Remote Control**: Control zoom from external applications
- **JSON Configuration**: Easy-to-edit configuration file
- **Visual Overlay**: Optional on-screen zoom indicator

## Installation

### Prerequisites

1. **OBS Studio 28.0+** with Python scripting enabled
2. **Python 3.8-3.11** (must match your OBS architecture)

### Install Dependencies

```bash
# Navigate to the script directory
cd /path/to/obs-zoom-to-mouse

# Install required packages
pip install -r requirements.txt
```

### Add to OBS

1. Open OBS Studio
2. Go to **Tools → Scripts**
3. Click the **Python Settings** tab and set your Python install path
4. Click the **Scripts** tab and click **+**
5. Navigate to and select `obs_zoom_to_mouse.py`

### Configure Hotkeys

1. Go to **Settings → Hotkeys**
2. Find "Toggle zoom to mouse" and assign a key
3. Find "Toggle follow mouse" and assign a key (optional)

## Configuration

### OBS Settings Panel

The script settings in OBS allow you to configure:

- **Zoom Source**: Select which display capture to zoom
- **Zoom Profile**: Choose a preset configuration
- **Zoom Factor**: How much to zoom in (1x - 5x)
- **Zoom Speed**: Animation speed
- **Auto Follow**: Automatically track mouse when zoomed
- **Follow Speed**: How fast to track the mouse
- **Follow Border**: Edge buffer before tracking activates
- **Animation Easing**: Choose animation style

### Configuration File (`config.json`)

For advanced configuration, edit `config.json`:

```json
{
  "version": "2.0.0",
  "default_profile": "standard",
  "profiles": {
    "standard": {
      "zoom_factor": 2.0,
      "zoom_speed": 0.06,
      "follow_speed": 0.25,
      "follow_border": 8,
      "easing": "ease_in_out",
      "auto_follow": true
    },
    "presentation": {
      "zoom_factor": 3.0,
      "zoom_speed": 0.1,
      "follow_speed": 0.3,
      "follow_border": 15,
      "easing": "ease_in_out"
    }
  },
  "websocket": {
    "enabled": false,
    "port": 8765
  },
  "display_overrides": {},
  "debug_logging": false
}
```

### Zoom Profiles

Create custom profiles for different use cases:

- **standard**: Balanced settings for general use
- **presentation**: Higher zoom for demos
- **quick**: Fast animations for quick highlighting

## WebSocket Remote Control

Enable WebSocket in `config.json` to control zoom from external applications.

### Protocol

Send JSON messages to the WebSocket server:

```json
// Toggle zoom
{"type": "toggle_zoom"}

// Toggle follow
{"type": "toggle_follow"}

// Set mouse position override
{"type": "mouse_position", "x": 100, "y": 200}

// Change profile
{"type": "set_profile", "profile": "presentation"}

// Clear mouse override
{"type": "clear_mouse"}
```

### Python Client Example

```python
import asyncio
import websockets
import json

async def toggle_zoom():
    async with websockets.connect("ws://localhost:8765") as ws:
        await ws.send(json.dumps({"type": "toggle_zoom"}))

asyncio.run(toggle_zoom())
```

## Easing Functions

Available animation styles:

| Name | Description |
|------|-------------|
| `linear` | No easing |
| `ease_in` | Slow start |
| `ease_out` | Slow end |
| `ease_in_out` | Slow start and end (default) |
| `elastic` | Bouncy overshoot |
| `bounce` | Bouncing effect |
| `ease_in_back` | Slight pullback then accelerate |
| `ease_out_back` | Overshoot then settle |

## Troubleshooting

### Mouse Position Incorrect

1. Check if `pynput` is installed: `pip install pynput`
2. On macOS, ensure accessibility permissions are granted
3. Try enabling debug logging to see coordinate values

### Retina/HiDPI Issues

The script automatically detects display scaling by comparing:
- Display dimensions from the source name (in points)
- Actual source dimensions from OBS (in pixels)

If automatic detection fails, manually set the scale in `config.json`:

```json
"display_overrides": {
  "display-uuid-here": {
    "scale_x": 2.0,
    "scale_y": 2.0
  }
}
```

### WebSocket Not Connecting

1. Ensure `websockets` is installed: `pip install websockets`
2. Check that the port (default 8765) is not in use
3. Enable debug logging to see server status

### Script Not Loading

1. Verify Python version matches OBS architecture (64-bit Python for 64-bit OBS)
2. Check OBS script log for error messages
3. Ensure all dependencies are installed in the correct Python environment

## File Structure

```
obs-zoom-to-mouse/
├── obs_zoom_to_mouse.py      # Main OBS script
├── config.json               # Configuration file
├── requirements.txt          # Python dependencies
├── README_PYTHON.md          # This file
├── obs-zoom-to-mouse.lua     # Legacy Lua version
└── zoom_core/                # Core modules
    ├── __init__.py
    ├── mouse_tracker.py      # Mouse position tracking
    ├── display_manager.py    # Display/monitor handling
    ├── zoom_controller.py    # Zoom state machine
    ├── config_manager.py     # Configuration management
    ├── easing.py             # Animation functions
    ├── websocket_server.py   # Remote control server
    └── visual_overlay.py     # On-screen indicator
```

## Migration from Lua Version

The Python version is a complete rewrite with a new architecture. Your existing Lua script settings are not automatically migrated.

Key differences:
- Configuration is now in `config.json` instead of OBS settings
- Multiple zoom profiles are supported
- WebSocket replaces UDP for remote control
- Automatic Retina detection (no manual scale settings needed in most cases)

## License

MIT License - See original repository for full license.

## Credits

- Original Lua script by [BlankSourceCode](https://github.com/BlankSourceCode/obs-zoom-to-mouse)
- Python rewrite with enhanced features

