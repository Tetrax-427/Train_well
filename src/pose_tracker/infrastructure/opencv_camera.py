from __future__ import annotations

import time

import cv2

from pose_tracker.domain.frame import Frame
from pose_tracker.errors import CameraError


class OpenCvCamera:
    def __init__(self, index: int, width: int, height: int, mirror: bool) -> None:
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise CameraError(f"Cannot open camera at index {index}")
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._mirror = mirror
        self._start = time.monotonic()

    def read(self) -> Frame | None:
        ok, image = self._capture.read()
        if not ok:
            return None
        if self._mirror:
            image = cv2.flip(image, 1)
        timestamp_ms = int((time.monotonic() - self._start) * 1000)
        return Frame(image=image, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        self._capture.release()