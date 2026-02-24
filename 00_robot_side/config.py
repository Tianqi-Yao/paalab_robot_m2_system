"""
机器人端配置
所有参数支持环境变量覆盖
"""

import os
import platform

# ── 串口配置 ──────────────────────────────────────────────
def _default_serial_port() -> str:
    """根据操作系统返回默认串口路径"""
    system = platform.system()
    if system == "Darwin":   # macOS
        return "/dev/cu.usbmodem14201"
    else:                    # Linux
        return "/dev/ttyACM0"

FEATHER_PORT: str = os.environ.get("FEATHER_PORT", _default_serial_port())
SERIAL_BAUD: int = int(os.environ.get("SERIAL_BAUD", "115200"))
SERIAL_TIMEOUT: float = float(os.environ.get("SERIAL_TIMEOUT", "1.0"))

# ── TCP 服务端配置 ─────────────────────────────────────────
TCP_HOST: str = os.environ.get("TCP_HOST", "0.0.0.0")   # 监听所有网卡
TCP_PORT: int = int(os.environ.get("TCP_PORT", "9000"))

# ── 看门狗配置 ────────────────────────────────────────────
WATCHDOG_TIMEOUT: float = float(os.environ.get("WATCHDOG_TIMEOUT", "2.0"))

# ── 允许写入串口的字符白名单 ──────────────────────────────
ALLOWED_COMMANDS: set = {"w", "s", "a", "d", " "}
HEARTBEAT_CHAR: str = "H"
