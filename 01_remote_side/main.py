"""
Remote-side launcher: keyboard control + video stream viewer.

Starts both RemoteSender (TCP + pynput) and RemoteViewer (MJPEG imshow)
in a single command.

Usage:
    export ROBOT_HOST=192.168.x.x   # required
    cd m2_system/01_remote_side
    python main.py

What runs:
    - Background daemon thread: RemoteSender
        → pynput keyboard → TCP:9000 → robot_receiver.py → serial → Feather M4
    - Main thread:        RemoteViewer
        → cv2.VideoCapture MJPEG → http://robot:8080 → cv2.imshow

Controls (keyboard focus must be on the terminal or active window):
    w / s / a / d  - move
    space          - stop
    Enter          - toggle auto state
    q              - quit everything

Press 'q' in the video window also quits both threads.
"""

import logging
import signal
import sys
import threading
from pathlib import Path

from config import STREAM_URL, ROBOT_HOST, TCP_PORT
from remote_sender import RemoteSender
from remote_viewer import RemoteViewer

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


def main() -> None:
    logger.info(f"Remote launcher starting (robot: {ROBOT_HOST}:{TCP_PORT})")
    logger.info(f"Stream URL: {STREAM_URL}")

    sender = RemoteSender()
    viewer = RemoteViewer(stream_url=STREAM_URL)

    def _shutdown(signum=None, frame=None) -> None:
        logger.info("Shutdown signal received, stopping all components...")
        sender.stop()
        viewer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # RemoteSender runs in a background daemon thread.
    # (pynput works from non-main threads on Linux via evdev.)
    sender_thread = threading.Thread(
        target=_run_sender, args=(sender,), daemon=True, name="remote_sender"
    )
    sender_thread.start()

    # RemoteViewer.run() blocks the main thread (cv2.imshow requires main thread).
    viewer.start()
    try:
        viewer.run()   # blocks until user presses 'q' or closes window
    except Exception as e:
        logger.error(f"Viewer error: {e}")
    finally:
        logger.info("Viewer exited, stopping sender...")
        sender.stop()
        logger.info("Remote launcher done")


def _run_sender(sender: RemoteSender) -> None:
    try:
        sender.run()
    except Exception as e:
        logger.error(f"Sender thread fatal error: {e}")


if __name__ == "__main__":
    main()
