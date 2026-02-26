"""
Remote-side keyboard controller + TCP command sender.

Captures keyboard input via pynput, sends motion commands and heartbeats
to the robot's TCP server (robot_receiver.py).

Usage (standalone):
    export ROBOT_HOST=192.168.x.x
    cd m2_system/01_remote_side
    python remote_sender.py

Controls:
    w / s / a / d  - forward / backward / turn left / turn right
    space          - emergency stop (also sent automatically on key release)
    Enter          - toggle STATE_AUTO_READY <-> STATE_AUTO_ACTIVE (once per press)
    q              - quit

Notes:
    - Heartbeat ('H') is sent every HEARTBEAT_INTERVAL seconds.
    - The robot-side watchdog triggers an emergency stop if no message arrives
      within WATCHDOG_TIMEOUT (2 s).
    - On TCP disconnect, the sender attempts to reconnect automatically.
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
    HEARTBEAT_INTERVAL,
    KEY_REPEAT_INTERVAL,
    ROBOT_HOST,
    TCP_PORT,
    TCP_RECONNECT_DELAY,
)

# ── Logging ─────────────────────────────────────────────────────────────────
_py_name = Path(__file__).stem
Path("log").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"log/{_py_name}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CONTROL_KEYS = frozenset({"w", "s", "a", "d"})
STOP_CHAR: str = " "
QUIT_KEY: str = "q"
HEARTBEAT_CHAR: str = "H"


class RemoteSender:
    """Keyboard controller that sends commands to the robot over TCP.

    Thread layout:
        - Heartbeat thread : sends 'H' every HEARTBEAT_INTERVAL seconds.
        - Key-repeat thread : sends current key (or stop) at KEY_REPEAT_INTERVAL.
        - Keyboard listener : pynput (may be called from main or a daemon thread).
    """

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._sock_lock = threading.Lock()

        self._running = False
        self._pressed_keys: set[str] = set()
        self._keys_lock = threading.Lock()
        self._enter_held: bool = False

        self._heartbeat_thread: threading.Thread | None = None
        self._repeat_thread: threading.Thread | None = None

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self) -> None:
        """Blocking entry point.  Connects to robot, starts threads, listens
        to keyboard.  Returns when 'q' is pressed or on fatal error."""
        self._running = True
        self._connect()

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        )
        self._heartbeat_thread.start()

        self._repeat_thread = threading.Thread(
            target=self._key_repeat_loop, daemon=True, name="key_repeat"
        )
        self._repeat_thread.start()

        logger.info(
            "Remote sender started (wasd: move, space: stop, Enter: toggle state, q: quit)"
        )
        logger.info(f"Target: {ROBOT_HOST}:{TCP_PORT}")

        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            while self._running:
                time.sleep(0.05)
            listener.stop()

        logger.info("Keyboard listener stopped")

    def stop(self) -> None:
        """Signal all threads to stop and close the socket."""
        logger.info("Stopping remote sender...")
        self._running = False
        self._close_socket()

    # ── Connection management ────────────────────────────────────────────────

    def _connect(self) -> None:
        """Try to connect (or reconnect) to the robot TCP server."""
        while self._running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((ROBOT_HOST, TCP_PORT))
                sock.settimeout(None)
                with self._sock_lock:
                    self._sock = sock
                logger.info(f"Connected to robot at {ROBOT_HOST}:{TCP_PORT}")
                return
            except OSError as e:
                logger.warning(
                    f"TCP connect failed ({ROBOT_HOST}:{TCP_PORT}): {e}  "
                    f"— retrying in {TCP_RECONNECT_DELAY}s"
                )
                time.sleep(TCP_RECONNECT_DELAY)

    def _close_socket(self) -> None:
        with self._sock_lock:
            if self._sock:
                try:
                    self._sock.close()
                except OSError as e:
                    logger.warning(f"Error closing socket: {e}")
                self._sock = None

    # ── Send helper ─────────────────────────────────────────────────────────

    def _send(self, char: str) -> None:
        """Send a single character; reconnect silently on failure."""
        with self._sock_lock:
            sock = self._sock

        if sock is None:
            return

        try:
            sock.sendall(char.encode("utf-8"))
        except OSError as e:
            logger.warning(f"Send failed: {e} — attempting reconnect")
            self._close_socket()
            threading.Thread(
                target=self._connect, daemon=True, name="reconnect"
            ).start()

    # ── Background threads ───────────────────────────────────────────────────

    def _heartbeat_loop(self) -> None:
        logger.info(f"Heartbeat thread started (interval: {HEARTBEAT_INTERVAL}s)")
        while self._running:
            self._send(HEARTBEAT_CHAR)
            time.sleep(HEARTBEAT_INTERVAL)

    def _key_repeat_loop(self) -> None:
        logger.info(
            f"Key-repeat thread started (rate: {1.0 / KEY_REPEAT_INTERVAL:.0f} Hz)"
        )
        while self._running:
            with self._keys_lock:
                active_keys = list(self._pressed_keys)

            if active_keys:
                self._send(active_keys[0])
                logger.debug(f"Repeat send: {repr(active_keys[0])}")
            else:
                self._send(STOP_CHAR)

            time.sleep(KEY_REPEAT_INTERVAL)

    # ── Keyboard callbacks ────────────────────────────────────────────────────

    def _on_press(self, key) -> None:
        char = _key_to_char(key)
        if char is None:
            return

        if char == QUIT_KEY:
            logger.info("Quit key 'q' pressed, exiting...")
            self._running = False
            return

        if char == "\r":
            if not self._enter_held:
                self._enter_held = True
                logger.info("Enter pressed → sending state toggle")
                self._send("\r")
            return

        if char in CONTROL_KEYS:
            with self._keys_lock:
                if char not in self._pressed_keys:
                    self._pressed_keys.add(char)
                    logger.info(f"Key pressed: {repr(char)}")
            self._send(char)

    def _on_release(self, key) -> None:
        char = _key_to_char(key)
        if char is None:
            return

        if char == "\r":
            self._enter_held = False
            return

        if char in CONTROL_KEYS:
            with self._keys_lock:
                self._pressed_keys.discard(char)
                remaining = len(self._pressed_keys)
            logger.debug(f"Key released: {repr(char)}, keys still held: {remaining}")

            if remaining == 0:
                self._send(STOP_CHAR)
                logger.info("All keys released, stop sent")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _key_to_char(key) -> str | None:
    try:
        if hasattr(key, "char") and key.char is not None:
            return key.char
        if key == keyboard.Key.space:
            return " "
        if key == keyboard.Key.enter:
            return "\r"
    except AttributeError:
        pass
    return None


# ── Standalone entry point ────────────────────────────────────────────────────

def main() -> None:
    sender = RemoteSender()

    def _signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        sender.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        sender.run()
    except Exception as e:
        logger.error(f"Remote sender fatal error: {e}")
        raise
    finally:
        sender.stop()


if __name__ == "__main__":
    main()
