from __future__ import annotations

import numpy as np
import pytest

from pose_tracker.application.frame_buffer import FrameBuffer
from pose_tracker.domain.frame import Frame


class MarkerEncoder:
    """Encodes a frame as one byte: its top-left pixel value (timestamp // 10)."""

    def __init__(self) -> None:
        self.fail = False

    def encode(self, image: np.ndarray) -> bytes | None:
        return None if self.fail else bytes([int(image[0, 0, 0])])


def frame(timestamp_ms: int) -> Frame:
    return Frame(np.full((2, 2, 3), timestamp_ms // 10, dtype=np.uint8), timestamp_ms)


def filled(timestamps: list[int], **kwargs: int) -> FrameBuffer:
    buffer = FrameBuffer(MarkerEncoder(), **kwargs)
    for t in timestamps:
        buffer.observe(frame(t))
    return buffer


def test_returns_the_closest_frame() -> None:
    buffer = filled([0, 100, 200, 300])
    assert buffer.nearest(190) == bytes([20])
    assert buffer.nearest(100) == bytes([10])


def test_empty_buffer_returns_none() -> None:
    assert FrameBuffer(MarkerEncoder()).nearest(0) is None


def test_old_frames_are_evicted() -> None:
    buffer = filled([0, 100, 200, 300, 400, 500], retention_ms=250, max_gap_ms=100)
    assert buffer.nearest(0) is None            # frame 0 is gone and 300 is too far
    assert buffer.nearest(300) == bytes([30])   # oldest survivor


def test_frame_too_far_from_the_request_is_not_returned() -> None:
    buffer = filled([0], max_gap_ms=500)
    assert buffer.nearest(500) == bytes([0])
    assert buffer.nearest(501) is None


def test_frames_that_fail_to_encode_are_skipped() -> None:
    encoder = MarkerEncoder()
    buffer = FrameBuffer(encoder)
    encoder.fail = True
    buffer.observe(frame(0))
    assert buffer.nearest(0) is None


def test_invalid_settings_rejected() -> None:
    with pytest.raises(ValueError):
        FrameBuffer(MarkerEncoder(), retention_ms=0)
    with pytest.raises(ValueError):
        FrameBuffer(MarkerEncoder(), max_gap_ms=-1)