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
    """OAK-D single-color-camera source via depthai.

    Streams BGR frames from the camera at the configured resolution.
    Optionally targets a specific OAK-D PoE device by IP address.

    Args:
        device_ip: IP address of the OAK-D PoE device.
                   Pass None to auto-detect via USB.
    """

    def __init__(self, device_ip: Optional[str] = None) -> None:
        self._device_ip = device_ip
        self._device = None
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

        xout_rgb = pipeline.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb")
        cam_rgb.preview.link(xout_rgb.input)

        try:
            if self._device_ip:
                device_info = dai.DeviceInfo(self._device_ip)
                self._device = dai.Device(pipeline, device_info)
            else:
                self._device = dai.Device(pipeline)
        except Exception as e:
            logger.error(f"Failed to open depthai device (ip={self._device_ip}): {e}")
            raise

        self._q_rgb = self._device.getOutputQueue(
            name="rgb", maxSize=1, blocking=False
        )
        logger.info(
            f"SimpleColorSource opened (device: {self._device_ip or 'USB/auto'},"
            f" {CAM_WIDTH}x{CAM_HEIGHT} @ {CAM_FPS}fps)"
        )

    def close(self) -> None:
        if self._device is not None:
            try:
                self._device.close()
            except Exception as e:
                logger.warning(f"Error closing depthai device: {e}")
            self._device = None
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
