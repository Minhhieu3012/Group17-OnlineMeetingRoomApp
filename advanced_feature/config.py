"""Central runtime configuration for HPH Meeting System.
Adjust ports/host here to match your environment.
This file also includes aliases for backward compatibility.
"""

# Network endpoints
SERVER_HOST = "127.0.0.1"   # or "0.0.0.0" on the server machine
TCP_PORT = 8888

# UDP media ports
UDP_PORT_VOICE = 9999
UDP_PORT_VIDEO = 10000

# Backwards-compat: single UDP port expected by some legacy code
UDP_PORT = UDP_PORT_VOICE

# WebSocket Gateway
GATEWAY_PORT = 8765  # name used by main.py
# (optional alias if other code expects WS_PORT)
WS_PORT = GATEWAY_PORT

# App meta
APP_NAME = "HPH Meeting"
