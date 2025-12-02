"""
WebSocket Server Module
Remote control via WebSocket protocol
"""

import json
import threading
import socket
from typing import Optional, Callable, Dict, Any, Tuple

# Try to import websockets for async WebSocket support
try:
    import asyncio
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class SimpleUDPServer:
    """
    Simple UDP server for backward compatibility with the Lua version.
    
    Accepts mouse position updates in the format "x y" (space-separated).
    """
    
    def __init__(self, port: int = 12345, poll_interval: int = 10):
        """
        Initialize UDP server.
        
        Args:
            port: UDP port to listen on
            poll_interval: Polling interval in milliseconds
        """
        self._port = port
        self._poll_interval = poll_interval
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self._mouse_position: Optional[Tuple[int, int]] = None
        self._on_message: Optional[Callable[[Dict[str, Any]], None]] = None
    
    @property
    def mouse_position(self) -> Optional[Tuple[int, int]]:
        """Get last received mouse position."""
        return self._mouse_position
    
    def set_message_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]):
        """Set callback for received messages."""
        self._on_message = callback
    
    def start(self) -> bool:
        """Start the UDP server."""
        if self._running:
            return True
        
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.setblocking(False)
            self._socket.bind(('', self._port))
            
            self._running = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            
            return True
        except Exception as e:
            print(f"Failed to start UDP server: {e}")
            return False
    
    def stop(self):
        """Stop the UDP server."""
        self._running = False
        
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
    
    def _poll_loop(self):
        """Poll loop for receiving messages."""
        while self._running and self._socket:
            try:
                data, addr = self._socket.recvfrom(1024)
                self._handle_message(data.decode('utf-8').strip())
            except BlockingIOError:
                pass
            except Exception:
                pass
            
            # Sleep for poll interval
            import time
            time.sleep(self._poll_interval / 1000.0)
    
    def _handle_message(self, message: str):
        """Handle received message."""
        try:
            # Try to parse as "x y" format
            parts = message.split()
            if len(parts) >= 2:
                x = int(parts[0])
                y = int(parts[1])
                self._mouse_position = (x, y)
                
                if self._on_message:
                    self._on_message({
                        'type': 'mouse_position',
                        'x': x,
                        'y': y
                    })
        except (ValueError, IndexError):
            pass


class WebSocketServer:
    """
    WebSocket server for remote control.
    
    Supports:
    - Mouse position updates
    - Zoom toggle commands
    - Profile switching
    - State updates to clients
    """
    
    def __init__(self, port: int = 8765):
        """
        Initialize WebSocket server.
        
        Args:
            port: Port to listen on
        """
        self._port = port
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        
        self._clients = set()
        self._mouse_position: Optional[Tuple[int, int]] = None
        
        # Callbacks
        self._on_toggle_zoom: Optional[Callable[[], None]] = None
        self._on_toggle_follow: Optional[Callable[[], None]] = None
        self._on_set_profile: Optional[Callable[[str], None]] = None
        self._on_mouse_position: Optional[Callable[[int, int], None]] = None
    
    @property
    def mouse_position(self) -> Optional[Tuple[int, int]]:
        """Get last received mouse position override."""
        return self._mouse_position
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    def set_callbacks(self,
                      on_toggle_zoom: Optional[Callable[[], None]] = None,
                      on_toggle_follow: Optional[Callable[[], None]] = None,
                      on_set_profile: Optional[Callable[[str], None]] = None,
                      on_mouse_position: Optional[Callable[[int, int], None]] = None):
        """
        Set callbacks for remote commands.
        
        Args:
            on_toggle_zoom: Called when zoom toggle is requested
            on_toggle_follow: Called when follow toggle is requested
            on_set_profile: Called when profile change is requested
            on_mouse_position: Called when mouse position is received
        """
        self._on_toggle_zoom = on_toggle_zoom
        self._on_toggle_follow = on_toggle_follow
        self._on_set_profile = on_set_profile
        self._on_mouse_position = on_mouse_position
    
    def start(self) -> bool:
        """Start the WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            print("WebSocket support not available. Install 'websockets' package.")
            return False
        
        if self._running:
            return True
        
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        return True
    
    def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
    
    def _run_server(self):
        """Run the server in a separate thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._server_main())
        except Exception as e:
            print(f"WebSocket server error: {e}")
        finally:
            self._loop.close()
            self._loop = None
    
    async def _server_main(self):
        """Main server coroutine."""
        async with websockets.serve(self._handle_client, "0.0.0.0", self._port):
            while self._running:
                await asyncio.sleep(0.1)
    
    async def _handle_client(self, websocket):
        """Handle a client connection."""
        self._clients.add(websocket)
        try:
            async for message in websocket:
                await self._handle_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
    
    async def _handle_message(self, message: str, websocket):
        """Handle a message from a client."""
        try:
            data = json.loads(message)
            msg_type = data.get('type', '')
            
            if msg_type == 'mouse_position':
                x = data.get('x', 0)
                y = data.get('y', 0)
                self._mouse_position = (x, y)
                if self._on_mouse_position:
                    self._on_mouse_position(x, y)
            
            elif msg_type == 'toggle_zoom':
                if self._on_toggle_zoom:
                    self._on_toggle_zoom()
            
            elif msg_type == 'toggle_follow':
                if self._on_toggle_follow:
                    self._on_toggle_follow()
            
            elif msg_type == 'set_profile':
                profile = data.get('profile', '')
                if self._on_set_profile and profile:
                    self._on_set_profile(profile)
            
            elif msg_type == 'clear_mouse':
                self._mouse_position = None
            
            elif msg_type == 'ping':
                await websocket.send(json.dumps({'type': 'pong'}))
        
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
    
    def broadcast_state(self, state: Dict[str, Any]):
        """
        Broadcast state update to all connected clients.
        
        Args:
            state: State dictionary to broadcast
        """
        if not self._clients or not self._loop:
            return
        
        message = json.dumps({
            'type': 'state_update',
            **state
        })
        
        async def _broadcast():
            for client in list(self._clients):
                try:
                    await client.send(message)
                except Exception:
                    self._clients.discard(client)
        
        try:
            asyncio.run_coroutine_threadsafe(_broadcast(), self._loop)
        except Exception:
            pass


# Factory function to get appropriate server
def create_server(server_type: str = 'websocket', **kwargs):
    """
    Create a server instance.
    
    Args:
        server_type: 'websocket' or 'udp'
        **kwargs: Server-specific arguments
        
    Returns:
        Server instance
    """
    if server_type == 'udp':
        return SimpleUDPServer(**kwargs)
    elif server_type == 'websocket':
        if WEBSOCKETS_AVAILABLE:
            return WebSocketServer(**kwargs)
        else:
            print("WebSocket not available, falling back to UDP")
            return SimpleUDPServer(**kwargs)
    else:
        raise ValueError(f"Unknown server type: {server_type}")

