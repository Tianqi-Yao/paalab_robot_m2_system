"""
Remote-side MJPEG video viewer.

Pulls frames from the robot's MJPEG HTTP stream and displays them
in an OpenCV window.  Reconnects automatically if the stream is lost.

Usage (standalone):
    export ROBOT_HOST=192.168.x.x
    cd m2_system/01_remote_side
    python remote_viewer.py

Press 'q' in the video window to quit.

Design:
    - A background thread reads frames from cv2.VideoCapture (MJPEG URL).
    - The main thread calls cv2.imshow (OpenCV requires the main thread).
    - If no new frame arrives for STREAM_STALE_TIMEOUT seconds, the thread
      closes and reopens cv2.VideoCapture (automatic reconnect).
"""

import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import STREAM_RECONNECT_DELAY, STREAM_STALE_TIMEOUT, STREAM_URL

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

WINDOW_NAME = "Robot Camera — press q to quit"


class RemoteViewer:
    """MJPEG viewer with background capture thread and auto-reconnect.

    Call start() to launch the background thread, then run() to enter
    the imshow loop (must be called from the main thread on most platforms).
    """

    def __init__(self, stream_url: str = STREAM_URL) -> None:
        self._url = stream_url
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._last_frame_time: float = 0.0

        self._running = False
        self._capture_thread: Optional[threading.Thread] = None

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the background frame-capture thread."""
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="frame_capture"
        )
        self._capture_thread.start()
        logger.info(f"Remote viewer started, stream URL: {self._url}")

    def stop(self) -> None:
        """Signal the capture thread to stop."""
        self._running = False
        logger.info("Remote viewer stopped")

    def run(self) -> None:
        """Blocking imshow loop.  Must be called from the main thread.

        Returns when the user presses 'q' or closes the window.
        """
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        placeholder = self._make_placeholder("Connecting to robot camera...")

        while self._running:
            with self._frame_lock:
                frame = self._latest_frame

            display = frame if frame is not None else placeholder

            # Check staleness and update placeholder text
            if frame is None or (
                self._last_frame_time > 0
                and (time.time() - self._last_frame_time) > STREAM_STALE_TIMEOUT
            ):
                display = self._make_placeholder("Stream lost — reconnecting...")

            try:
                cv2.imshow(WINDOW_NAME, display)
            except cv2.error as e:
                logger.error(f"cv2.imshow error: {e}")
                break

            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                logger.info("'q' pressed in video window, quitting viewer")
                break

            # Window close button
            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    logger.info("Video window closed, quitting viewer")
                    break
            except cv2.error:
                break

        self.stop()
        cv2.destroyAllWindows()

    # ── Internal ────────────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Background thread: continuously reads frames from MJPEG stream."""
        logger.info("Capture thread started")
        while self._running:
            cap = self._open_capture()
            if cap is None:
                time.sleep(STREAM_RECONNECT_DELAY)
                continue

            logger.info("Stream opened, reading frames")
            while self._running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    logger.warning("Frame read failed — stream may have dropped")
                    break

                with self._frame_lock:
                    self._latest_frame = frame
                    self._last_frame_time = time.time()

            cap.release()
            if self._running:
                logger.info(
                    f"Stream disconnected, retrying in {STREAM_RECONNECT_DELAY}s..."
                )
                with self._frame_lock:
                    self._latest_frame = None
                time.sleep(STREAM_RECONNECT_DELAY)

        logger.info("Capture thread exiting")

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        """Try to open the MJPEG stream.  Returns None on failure."""
        try:
            cap = cv2.VideoCapture(self._url)
            if not cap.isOpened():
                logger.warning(f"Cannot open stream: {self._url}")
                cap.release()
                return None
            return cap
        except Exception as e:
            logger.error(f"Error opening VideoCapture: {e}")
            return None

    @staticmethod
    def _make_placeholder(text: str) -> np.ndarray:
        """Return a dark frame with a status message."""
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(
            img, text,
            (20, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (200, 200, 200),
            2,
            cv2.LINE_AA,
        )
        return img


# ── Standalone entry point ────────────────────────────────────────────────────

def main() -> None:
    viewer = RemoteViewer()

    def _signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, stopping viewer...")
        viewer.stop()
        cv2.destroyAllWindows()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        viewer.start()
        viewer.run()   # blocks until user quits
    except Exception as e:
        logger.error(f"Remote viewer fatal error: {e}")
        raise
    finally:
        viewer.stop()


if __name__ == "__main__":
    main()
