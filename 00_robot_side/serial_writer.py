"""
线程安全串口写入封装
"""

import logging
import threading
from pathlib import Path

import serial

from config import FEATHER_PORT, SERIAL_BAUD, SERIAL_TIMEOUT, ALLOWED_COMMANDS

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


class SerialWriter:
    """线程安全的串口写入封装"""

    def __init__(self, port: str = FEATHER_PORT, baud: int = SERIAL_BAUD) -> None:
        self._port = port
        self._baud = baud
        self._lock = threading.Lock()
        self._ser: serial.Serial | None = None

    def open(self) -> None:
        """打开串口，失败时抛出异常"""
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=SERIAL_TIMEOUT)
            logger.info(f"串口已打开: {self._port} @ {self._baud} baud")
        except serial.SerialException as e:
            logger.error(f"串口打开失败 [{self._port}]: {e}")
            raise

    def close(self) -> None:
        """关闭串口"""
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
                logger.info("串口已关闭")

    def write_command(self, char: str) -> None:
        """
        写入单个控制字符到串口（白名单过滤）
        只允许 w/s/a/d/空格，其余字符记警告并丢弃
        """
        if char not in ALLOWED_COMMANDS:
            logger.warning(f"非法命令字符被拦截: {repr(char)}")
            return

        self._write_raw(char.encode())

    def emergency_stop(self) -> None:
        """立即发送急停（空格）到串口，看门狗超时时调用"""
        logger.warning("急停触发！发送空格到串口")
        self._write_raw(b" ")

    def _write_raw(self, data: bytes) -> None:
        """底层串口写入，加锁保护"""
        with self._lock:
            if self._ser is None or not self._ser.is_open:
                logger.error("串口未打开，无法写入")
                return
            try:
                self._ser.write(data)
                logger.debug(f"串口写入: {repr(data)}")
            except serial.SerialException as e:
                logger.error(f"串口写入失败: {e}")
                raise

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open
