from __future__ import annotations

import cv2
import numpy as np


class OpenCvJpegEncoder:
    """Downscales to ``max_width`` (never upscales) and encodes as JPEG."""

    def __init__(self, max_width: int = 640, quality: int = 80) -> None:
        if max_width <= 0 or not 1 <= quality <= 100:
            raise ValueError("max_width must be positive and quality within 1..100")
        self._max_width = max_width
        self._quality = quality

    def encode(self, image: np.ndarray) -> bytes | None:
        height, width = image.shape[:2]
        if width > self._max_width:
            scale = self._max_width / width
            image = cv2.resize(
                image,
                (self._max_width, max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        return buffer.tobytes() if ok else None