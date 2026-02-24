"""
看门狗定时器
客户端连接时 start()，每条消息调用 reset()，断开时 stop()
超时未收到消息则自动触发急停回调
"""

import logging
import threading
from pathlib import Path
from typing import Callable

from config import WATCHDOG_TIMEOUT

# ── 日志配置 ──────────────────────────────────────────────
_py_name = Path(__file__).stem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{_py_name}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class Watchdog:
    """
    超时看门狗
    若 timeout 秒内未收到 reset()，自动调用 on_timeout 回调（急停）
    """

    def __init__(self, timeout: float = WATCHDOG_TIMEOUT, on_timeout: Callable = None) -> None:
        self._timeout = timeout
        self._on_timeout = on_timeout or self._default_timeout_handler
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._active = False

    def start(self) -> None:
        """启动看门狗（客户端连接时调用）"""
        with self._lock:
            self._active = True
            self._schedule()
        logger.info(f"看门狗已启动，超时时间: {self._timeout}s")

    def reset(self) -> None:
        """重置超时计时（收到任意有效消息时调用）"""
        with self._lock:
            if not self._active:
                return
            self._cancel()
            self._schedule()

    def stop(self) -> None:
        """停止看门狗（客户端正常断开时调用，不触发急停）"""
        with self._lock:
            self._active = False
            self._cancel()
        logger.info("看门狗已停止")

    def _schedule(self) -> None:
        """内部：创建新定时器（必须在 _lock 保护下调用）"""
        self._timer = threading.Timer(self._timeout, self._trigger)
        self._timer.daemon = True
        self._timer.start()

    def _cancel(self) -> None:
        """内部：取消当前定时器（必须在 _lock 保护下调用）"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _trigger(self) -> None:
        """内部：超时触发，调用急停回调"""
        logger.warning(f"看门狗超时！{self._timeout}s 内未收到消息，触发急停")
        try:
            self._on_timeout()
        except Exception as e:
            logger.error(f"急停回调执行出错: {e}")

    @staticmethod
    def _default_timeout_handler() -> None:
        logger.error("看门狗超时：未设置急停回调！")
