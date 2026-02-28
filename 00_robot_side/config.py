"""
Robot-side configuration.
All parameters can be overridden via environment variables.

Environment variable quick reference:
  FEATHER_PORT, SERIAL_BAUD, SERIAL_TIMEOUT
  TCP_HOST, TCP_PORT
  WATCHDOG_TIMEOUT
  CAM1_IP, CAM2_IP, CAM1_STREAM_PORT, CAM2_STREAM_PORT
  CAM_FPS, CAM_WIDTH, CAM_HEIGHT, MJPEG_QUALITY, LOCAL_DISPLAY
  KEY_REPEAT_INTERVAL
  WEB_HTTP_PORT, WEB_WS_PORT
  MAX_LINEAR_VEL, MAX_ANGULAR_VEL
  RTK_PORT, RTK_BAUD, RTK_TIMEOUT, RTK_ENABLED
  DATA_LOG_DIR
  NAV_LOOKAHEAD_M, NAV_DECEL_RADIUS_M, NAV_ARRIVE_FRAMES, NAV_GPS_TIMEOUT_S
  NAV_PID_KP, NAV_PID_KI, NAV_PID_KD, NAV_MA_WINDOW
"""

import os
import platform

# ═══════════════════════════════════════════════════════
# 串口（Feather M4 CAN 连接）
# ═══════════════════════════════════════════════════════
def _default_serial_port() -> str:
    """Return the default serial port path based on the current OS."""
    system = platform.system()
    if system == "Darwin":   # macOS
        return "/dev/cu.usbmodem2301"
    else:                    # Linux
        return "/dev/ttyACM0"

FEATHER_PORT: str   = os.environ.get("FEATHER_PORT", _default_serial_port())
SERIAL_BAUD: int    = int(os.environ.get("SERIAL_BAUD",    "115200"))
SERIAL_TIMEOUT: float = float(os.environ.get("SERIAL_TIMEOUT", "1.0"))

# Allowed command characters (serial whitelist for legacy WASD mode)
ALLOWED_COMMANDS: set = {"w", "s", "a", "d", " ", "\r"}
HEARTBEAT_CHAR: str   = "H"

# ═══════════════════════════════════════════════════════
# 网络（TCP 遥控服务端，供 remote_sender.py 使用）
# ═══════════════════════════════════════════════════════
TCP_HOST: str = os.environ.get("TCP_HOST", "0.0.0.0")   # listen on all interfaces
TCP_PORT: int = int(os.environ.get("TCP_PORT", "9000"))

# ═══════════════════════════════════════════════════════
# 看门狗
# ═══════════════════════════════════════════════════════
WATCHDOG_TIMEOUT: float = float(os.environ.get("WATCHDOG_TIMEOUT", "2.0"))

# ═══════════════════════════════════════════════════════
# 摄像头（OAK-D PoE + MJPEG 流）
# ═══════════════════════════════════════════════════════
CAM1_IP: str = os.environ.get("CAM1_IP", "10.95.76.10")
CAM2_IP: str = os.environ.get("CAM2_IP", "10.95.76.11")

CAM1_STREAM_PORT: int = int(os.environ.get("CAM1_STREAM_PORT", "8080"))
CAM2_STREAM_PORT: int = int(os.environ.get("CAM2_STREAM_PORT", "8081"))

CAM_FPS: int       = int(os.environ.get("CAM_FPS",       "30"))
CAM_WIDTH: int     = int(os.environ.get("CAM_WIDTH",     "1280"))
CAM_HEIGHT: int    = int(os.environ.get("CAM_HEIGHT",    "720"))
MJPEG_QUALITY: int = int(os.environ.get("MJPEG_QUALITY", "80"))   # 1-100
LOCAL_DISPLAY: bool = os.environ.get("LOCAL_DISPLAY", "0") == "1"

# ═══════════════════════════════════════════════════════
# Web 摇杆控制器（HTTP + WebSocket）
# ═══════════════════════════════════════════════════════
WEB_HTTP_PORT: int = int(os.environ.get("WEB_HTTP_PORT", "8888"))
WEB_WS_PORT:   int = int(os.environ.get("WEB_WS_PORT",   "8889"))

MAX_LINEAR_VEL:  float = float(os.environ.get("MAX_LINEAR_VEL",  "1.0"))  # m/s
MAX_ANGULAR_VEL: float = float(os.environ.get("MAX_ANGULAR_VEL", "1.0"))  # rad/s

# ═══════════════════════════════════════════════════════
# 传感器：RTK GPS（Emlid RS+）
# ═══════════════════════════════════════════════════════
RTK_PORT:    str   = os.environ.get("RTK_PORT",    "/dev/cu.usbmodem2403")
RTK_BAUD:    int   = int(os.environ.get("RTK_BAUD",    "9600"))
RTK_TIMEOUT: float = float(os.environ.get("RTK_TIMEOUT", "1.0"))
RTK_ENABLED: bool  = os.environ.get("RTK_ENABLED", "1") == "1"

# ═══════════════════════════════════════════════════════
# 数据录制
# ═══════════════════════════════════════════════════════
DATA_LOG_DIR: str = os.environ.get("DATA_LOG_DIR", "data_log")

# ═══════════════════════════════════════════════════════
# 导航（路径跟踪 / GPS 滤波）
# ═══════════════════════════════════════════════════════
KEY_REPEAT_INTERVAL: float = float(os.environ.get("KEY_REPEAT_INTERVAL", "0.1"))  # Hz: 1/0.1 = 10 Hz

NAV_LOOKAHEAD_M:    float = float(os.environ.get("NAV_LOOKAHEAD_M",    "2.0"))   # Pure Pursuit lookahead
NAV_DECEL_RADIUS_M: float = float(os.environ.get("NAV_DECEL_RADIUS_M", "3.0"))   # 减速圆半径
NAV_ARRIVE_FRAMES:  int   = int(os.environ.get("NAV_ARRIVE_FRAMES",    "5"))     # 连续帧到达判定
NAV_GPS_TIMEOUT_S:  float = float(os.environ.get("NAV_GPS_TIMEOUT_S",  "5.0"))   # GPS 超时停止
NAV_PID_KP:         float = float(os.environ.get("NAV_PID_KP",         "0.8"))
NAV_PID_KI:         float = float(os.environ.get("NAV_PID_KI",         "0.01"))
NAV_PID_KD:         float = float(os.environ.get("NAV_PID_KD",         "0.05"))
NAV_MA_WINDOW:      int   = int(os.environ.get("NAV_MA_WINDOW",        "10"))    # 移动平均窗口大小
