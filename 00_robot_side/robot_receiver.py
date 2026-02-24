"""
机器人端主程序
TCP 服务端：单连接模式，接收键盘指令 + 心跳，转发到 Feather M4 CAN 串口

启动方式：
    export FEATHER_PORT=/dev/cu.usbmodem14201   # macOS，可选
    python robot_receiver.py
"""

import logging
import signal
import socket
import sys
from pathlib import Path

from config import (
    FEATHER_PORT,
    HEARTBEAT_CHAR,
    TCP_HOST,
    TCP_PORT,
    WATCHDOG_TIMEOUT,
)
from serial_writer import SerialWriter
from watchdog import Watchdog

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


class RobotReceiver:
    """TCP 服务端：接收远程键盘指令并转发到串口"""

    def __init__(self) -> None:
        self._serial = SerialWriter()
        self._watchdog = Watchdog(
            timeout=WATCHDOG_TIMEOUT,
            on_timeout=self._on_watchdog_timeout,
        )
        self._server_sock: socket.socket | None = None
        self._running = False

    # ── 初始化 ────────────────────────────────────────────

    def setup(self) -> None:
        """打开串口，创建 TCP 服务端 socket"""
        self._serial.open()
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((TCP_HOST, TCP_PORT))
        self._server_sock.listen(1)   # 单连接模式
        logger.info(f"TCP 服务端已启动，监听 {TCP_HOST}:{TCP_PORT}")
        logger.info(f"串口: {FEATHER_PORT}，看门狗超时: {WATCHDOG_TIMEOUT}s")

    # ── 主循环 ────────────────────────────────────────────

    def run(self) -> None:
        """主循环：持续等待客户端连接，断开后重新等待"""
        self._running = True
        while self._running:
            logger.info("等待远程端连接…")
            try:
                client_sock, addr = self._server_sock.accept()
            except OSError as e:
                if self._running:
                    logger.error(f"accept() 失败: {e}")
                break

            logger.info(f"远程端已连接: {addr}")
            self._watchdog.start()
            try:
                self._handle_client(client_sock)
            finally:
                self._watchdog.stop()
                self._serial.emergency_stop()
                client_sock.close()
                logger.info(f"远程端已断开: {addr}，已发送急停")

    def _handle_client(self, sock: socket.socket) -> None:
        """处理单个客户端连接，逐字节读取并分发指令"""
        while True:
            try:
                data = sock.recv(1)
            except OSError as e:
                logger.warning(f"recv 异常，连接中断: {e}")
                break

            if not data:
                # TCP 正常关闭（recv 返回空字节）
                logger.info("远程端正常关闭连接")
                break

            char = data.decode("utf-8", errors="ignore")
            self._dispatch(char)

    def _dispatch(self, char: str) -> None:
        """根据收到的字符分发处理逻辑"""
        if char == HEARTBEAT_CHAR:
            # 心跳：只重置看门狗，不写串口
            self._watchdog.reset()
            logger.debug("收到心跳 H，看门狗已重置")
        else:
            # 控制指令：重置看门狗 + 写串口（serial_writer 内部做白名单过滤）
            self._watchdog.reset()
            self._serial.write_command(char)
            logger.info(f"收到指令: {repr(char)}，已写入串口")

    # ── 看门狗超时回调 ────────────────────────────────────

    def _on_watchdog_timeout(self) -> None:
        """看门狗超时时触发急停（在定时器线程中执行）"""
        self._serial.emergency_stop()

    # ── 优雅关闭 ──────────────────────────────────────────

    def shutdown(self) -> None:
        """优雅关闭：停止主循环，关闭 socket 和串口"""
        logger.info("正在关闭机器人端…")
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError as e:
                logger.warning(f"关闭服务端 socket 时出错: {e}")
        self._watchdog.stop()
        self._serial.close()
        logger.info("机器人端已关闭")


# ── 入口 ──────────────────────────────────────────────────

def main() -> None:
    receiver = RobotReceiver()

    def _signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，开始优雅关闭…")
        receiver.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        receiver.setup()
        receiver.run()
    except Exception as e:
        logger.error(f"机器人端运行出错: {e}")
        raise
    finally:
        receiver.shutdown()


if __name__ == "__main__":
    main()
