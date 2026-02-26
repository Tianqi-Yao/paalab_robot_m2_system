"""
Remote-side configuration.
All parameters can be overridden via environment variables.

Required:
    export ROBOT_HOST=192.168.x.x   # IP address of the robot (Mac Mini)

Optional overrides:
    export TCP_PORT=9000
    export STREAM_PORT=8080
    export HEARTBEAT_INTERVAL=0.5
    export KEY_REPEAT_INTERVAL=0.1
"""

import os

# ── Robot connection ────────────────────────────────────────────────────────
ROBOT_HOST: str = os.environ.get("ROBOT_HOST", "10.95.76.100")

# ── Control channel (TCP) ───────────────────────────────────────────────────
TCP_PORT: int = int(os.environ.get("TCP_PORT", "9000"))

# ── Video stream channel (MJPEG over HTTP) ──────────────────────────────────
STREAM_PORT: int = int(os.environ.get("STREAM_PORT", "8080"))
STREAM_URL: str = f"http://{ROBOT_HOST}:{STREAM_PORT}"

# ── Timing ──────────────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL: float = float(os.environ.get("HEARTBEAT_INTERVAL", "0.5"))
KEY_REPEAT_INTERVAL: float = float(os.environ.get("KEY_REPEAT_INTERVAL", "0.1"))

# ── Reconnection ────────────────────────────────────────────────────────────
TCP_RECONNECT_DELAY: float = float(os.environ.get("TCP_RECONNECT_DELAY", "2.0"))
STREAM_RECONNECT_DELAY: float = float(os.environ.get("STREAM_RECONNECT_DELAY", "3.0"))
STREAM_STALE_TIMEOUT: float = float(os.environ.get("STREAM_STALE_TIMEOUT", "3.0"))
