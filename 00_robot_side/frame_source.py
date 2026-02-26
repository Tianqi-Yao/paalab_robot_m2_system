"""
Pluggable frame source interface for MJPEG streaming.

To add a new processing pipeline, subclass FrameSource and implement
open() / close() / get_frame().  The MJPEGServer in camera_streamer.py
accepts any FrameSource — no other changes needed.

Example future sources:
    class YOLODetectionSource(FrameSource): ...   # bounding-box overlay
    class DepthAlignSource(FrameSource): ...       # color + depth side-by-side
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class FrameSource(ABC):
    """Abstract base class for frame providers."""

    @abstractmethod
    def open(self) -> None:
        """Initialize resources (camera pipeline, model weights, etc.)."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release all acquired resources."""
        ...

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest BGR frame, or None if not yet available."""
        ...


class SimpleColorSource(FrameSource):
    """OAK-D single-color-camera source via depthai (v3 API).

    Streams BGR frames from the camera at the configured resolution.
    Optionally targets a specific OAK-D PoE device by IP address.

    depthai v3 changes vs v2:
    - XLinkOut node removed → use cam.output.createOutputQueue() directly
    - dai.Device(pipeline) removed → pipeline.start([device_info]) manages device
    - device.getOutputQueue() removed → queue obtained from node output before start

    Args:
        device_ip: IP address of the OAK-D PoE device.
                   Pass None to auto-detect via USB.
    """

    def __init__(self, device_ip: Optional[str] = None) -> None:
        self._device_ip = device_ip
        self._pipeline = None
        self._q_rgb = None

    def open(self) -> None:
        import depthai as dai

        from config import CAM_FPS, CAM_HEIGHT, CAM_WIDTH

        pipeline = dai.Pipeline()

        cam_rgb = pipeline.create(dai.node.ColorCamera)
        cam_rgb.setPreviewSize(CAM_WIDTH, CAM_HEIGHT)
        cam_rgb.setInterleaved(False)
        cam_rgb.setFps(CAM_FPS)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

        # v3: createOutputQueue() on the node output replaces XLinkOut node
        self._q_rgb = cam_rgb.preview.createOutputQueue(maxSize=1, blocking=False)

        try:
            if self._device_ip:
                device_info = dai.DeviceInfo(self._device_ip)
                pipeline.start(device_info)
            else:
                pipeline.start()
        except Exception as e:
            logger.error(f"Failed to start depthai pipeline (ip={self._device_ip}): {e}")
            self._q_rgb = None
            raise

        self._pipeline = pipeline
        logger.info(
            f"SimpleColorSource opened (device: {self._device_ip or 'USB/auto'},"
            f" {CAM_WIDTH}x{CAM_HEIGHT} @ {CAM_FPS}fps)"
        )

    def close(self) -> None:
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            except Exception as e:
                logger.warning(f"Error stopping depthai pipeline: {e}")
            self._pipeline = None
        self._q_rgb = None
        logger.info(f"SimpleColorSource closed (device: {self._device_ip or 'USB/auto'})")

    def get_frame(self) -> Optional[np.ndarray]:
        if self._q_rgb is None:
            return None
        try:
            in_rgb = self._q_rgb.tryGet()
            if in_rgb is not None:
                return in_rgb.getCvFrame()
        except Exception as e:
            logger.error(f"Error getting frame from depthai queue: {e}")
        return None
