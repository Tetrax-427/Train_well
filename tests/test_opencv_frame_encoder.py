from __future__ import annotations

import cv2
import numpy as np
import pytest

from pose_tracker.infrastructure.opencv_frame_encoder import OpenCvJpegEncoder


def decode(jpeg: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)


def test_wide_images_are_downscaled_and_encoded_as_jpeg() -> None:
    jpeg = OpenCvJpegEncoder(max_width=320).encode(np.zeros((360, 640, 3), dtype=np.uint8))
    assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
    assert decode(jpeg).shape[:2] == (180, 320)


def test_small_images_are_not_upscaled() -> None:
    jpeg = OpenCvJpegEncoder(max_width=320).encode(np.zeros((50, 100, 3), dtype=np.uint8))
    assert jpeg is not None
    assert decode(jpeg).shape[:2] == (50, 100)


def test_invalid_settings_rejected() -> None:
    with pytest.raises(ValueError):
        OpenCvJpegEncoder(max_width=0)
    with pytest.raises(ValueError):
        OpenCvJpegEncoder(quality=101)