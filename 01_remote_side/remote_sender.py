"""
远程端主程序
pynput 全局键盘捕获 + TCP 客户端 + 心跳线程

启动方式：
    export ROBOT_HOST=192.168.x.x   # Mac Mini 的 LAN IP
    python remote_sender.py

控制键：
    w / s / a / d  - 前进 / 后退 / 左转 / 右转
    空格           - 急停（松开所有键时自动发送）
    q              - 退出程序
"""

import logging
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from pynput import keyboard

from config import (
    CONTROL_KEYS,
    HEARTBEAT_CHAR,
    HEARTBEAT_INTERVAL,
    KEY_REPEAT_INTERVAL,
    QUIT_KEY,
    ROBOT_HOST,
    ROBOT_PORT,
    STOP_CHAR,
)

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


class RemoteSender:
    """远程键盘控制发送端"""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._running = False

        # 当前按下的控制键集合，Lock 保护
        self._pressed_keys: set[str] = set()
        self._keys_lock = threading.Lock()

        # 后台线程
        self._heartbeat_thread: threading.Thread | None = None
        self._repeat_thread: threading.Thread | None = None

    # ── 网络连接 ──────────────────────────────────────────

    def connect(self) -> None:
        """连接到机器人端 TCP 服务器"""
        logger.info(f"正在连接机器人端 {ROBOT_HOST}:{ROBOT_PORT}…")
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((ROBOT_HOST, ROBOT_PORT))
            logger.info(f"已连接到机器人端: {ROBOT_HOST}:{ROBOT_PORT}")
        except OSError as e:
            logger.error(f"连接机器人端失败 [{ROBOT_HOST}:{ROBOT_PORT}]: {e}")
            raise

    def _send(self, char: str) -> bool:
        """发送单字节字符，返回 True 表示成功，False 表示连接断开"""
        if self._sock is None:
            return False
        try:
            self._sock.sendall(char.encode("utf-8"))
            return True
        except OSError as e:
            logger.error(f"发送失败，连接已断开: {e}")
            return False

    # ── 后台线程 ──────────────────────────────────────────

    def _heartbeat_loop(self) -> None:
        """心跳线程：每 HEARTBEAT_INTERVAL 秒发送一次 'H'"""
        logger.info(f"心跳线程已启动，间隔: {HEARTBEAT_INTERVAL}s")
        while self._running:
            if not self._send(HEARTBEAT_CHAR):
                logger.warning("心跳发送失败，连接可能已断开")
                self._running = False
                break
            logger.debug("心跳已发送: H")
            time.sleep(HEARTBEAT_INTERVAL)

    def _key_repeat_loop(self) -> None:
        """
        按键重复线程：10Hz 持续发送当前按下的控制键
        无按键时发送急停（空格）
        """
        logger.info(f"按键重复线程已启动，频率: {1.0/KEY_REPEAT_INTERVAL:.0f}Hz")
        while self._running:
            with self._keys_lock:
                active_keys = list(self._pressed_keys)

            if active_keys:
                # 发送优先级最高的按键（取第一个）
                char = active_keys[0]
                if not self._send(char):
                    self._running = False
                    break
                logger.debug(f"重复发送: {repr(char)}")
            else:
                # 无按键时持续发送急停
                if not self._send(STOP_CHAR):
                    self._running = False
                    break

            time.sleep(KEY_REPEAT_INTERVAL)

    # ── 键盘监听回调 ──────────────────────────────────────

    def _on_press(self, key) -> None:
        """按键按下回调"""
        char = self._key_to_char(key)
        if char is None:
            return

        if char == QUIT_KEY:
            logger.info("收到退出键 'q'，正在退出…")
            self._running = False
            return

        if char in CONTROL_KEYS:
            send_char = CONTROL_KEYS[char]
            with self._keys_lock:
                if send_char not in self._pressed_keys:
                    self._pressed_keys.add(send_char)
                    logger.info(f"按键按下: {repr(char)} -> 发送 {repr(send_char)}")
            # 立即发送一次（额外的即时响应）
            self._send(send_char)

    def _on_release(self, key) -> None:
        """按键松开回调"""
        char = self._key_to_char(key)
        if char is None:
            return

        if char in CONTROL_KEYS:
            send_char = CONTROL_KEYS[char]
            with self._keys_lock:
                self._pressed_keys.discard(send_char)
                remaining = len(self._pressed_keys)
            logger.debug(f"按键松开: {repr(char)}，剩余按键数: {remaining}")

            # 所有键松开后立即发一次急停
            if remaining == 0:
                self._send(STOP_CHAR)
                logger.info("所有键已松开，发送急停")

    @staticmethod
    def _key_to_char(key) -> str | None:
        """将 pynput Key 对象转换为字符串，无效则返回 None"""
        try:
            # 普通字符键
            if hasattr(key, "char") and key.char is not None:
                return key.char
            # 空格键
            if key == keyboard.Key.space:
                return " "
        except AttributeError:
            pass
        return None

    # ── 主流程 ────────────────────────────────────────────

    def run(self) -> None:
        """启动所有线程并开始键盘监听"""
        self._running = True

        # 启动心跳线程
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        )
        self._heartbeat_thread.start()

        # 启动按键重复线程
        self._repeat_thread = threading.Thread(
            target=self._key_repeat_loop, daemon=True, name="key_repeat"
        )
        self._repeat_thread.start()

        logger.info("键盘监听已启动（wasd 控制，空格急停，q 退出）")
        logger.info(f"连接目标: {ROBOT_HOST}:{ROBOT_PORT}")

        # pynput 监听（阻塞直到 _running=False 或异常）
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            while self._running:
                time.sleep(0.05)
            listener.stop()

        logger.info("键盘监听已停止")

    def shutdown(self) -> None:
        """优雅关闭：发送急停，等待线程结束，关闭 socket"""
        logger.info("正在关闭远程端…")
        self._running = False

        # 发送最终急停
        self._send(STOP_CHAR)
        logger.info("已发送最终急停指令")

        # 等待后台线程结束
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        if self._repeat_thread and self._repeat_thread.is_alive():
            self._repeat_thread.join(timeout=2.0)

        # 关闭 socket
        if self._sock:
            try:
                self._sock.close()
            except OSError as e:
                logger.warning(f"关闭 socket 时出错: {e}")

        logger.info("远程端已关闭")


# ── 入口 ──────────────────────────────────────────────────

def main() -> None:
    sender = RemoteSender()

    def _signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，开始优雅关闭…")
        sender.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        sender.connect()
        sender.run()
    except Exception as e:
        logger.error(f"远程端运行出错: {e}")
        raise
    finally:
        sender.shutdown()


if __name__ == "__main__":
    main()
