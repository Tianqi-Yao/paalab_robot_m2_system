"""
远程端配置
所有参数支持环境变量覆盖
"""

import os

# ── 连接配置 ──────────────────────────────────────────────
ROBOT_HOST: str = os.environ.get("ROBOT_HOST", "192.168.1.100")  # 机器人端（Mac Mini）IP
ROBOT_PORT: int = int(os.environ.get("ROBOT_PORT", "9000"))

# ── 心跳配置（必须远小于看门狗超时 2.0s）────────────────
HEARTBEAT_INTERVAL: float = float(os.environ.get("HEARTBEAT_INTERVAL", "0.5"))

# ── 按键重复发送间隔（10 Hz）─────────────────────────────
KEY_REPEAT_INTERVAL: float = float(os.environ.get("KEY_REPEAT_INTERVAL", "0.1"))

# ── 控制键映射 ────────────────────────────────────────────
# pynput Key 字符 -> 发送到机器人的字节
CONTROL_KEYS: dict = {
    "w": "w",
    "s": "s",
    "a": "a",
    "d": "d",
}
STOP_CHAR: str = " "       # 急停字符
HEARTBEAT_CHAR: str = "H"  # 心跳字符
QUIT_KEY: str = "q"        # 退出键
