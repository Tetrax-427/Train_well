from __future__ import annotations

from collections import deque

from pose_tracker.domain.frame import Frame
from pose_tracker.interfaces import FrameEncoder


class FrameBuffer:
    """Rolling window of recent camera frames, kept as encoded JPEGs to bound memory.

    Acts as a FrameObserver (fed by the pipeline) and as a SnapshotSource (queried
    when a rep finishes).
    """

    def __init__(
        self,
        encoder: FrameEncoder,
        retention_ms: int = 15_000,
        max_gap_ms: int = 500,
        min_interval_ms: int = 0,
    ) -> None:
        if retention_ms <= 0 or max_gap_ms < 0 or min_interval_ms < 0:
            raise ValueError(
                "retention_ms must be positive; max_gap_ms and min_interval_ms non-negative"
            )
        self._encoder = encoder
        self._retention_ms = retention_ms
        self._max_gap_ms = max_gap_ms
        self._min_interval_ms = min_interval_ms
        self._last_kept_ms: int | None = None
        self._frames: deque[tuple[int, bytes]] = deque()

    def observe(self, frame: Frame) -> None:
        if (
            self._last_kept_ms is not None
            and frame.timestamp_ms - self._last_kept_ms < self._min_interval_ms
        ):
            return
        jpeg = self._encoder.encode(frame.image)
        if jpeg is None:
            return
        self._frames.append((frame.timestamp_ms, jpeg))
        self._last_kept_ms = frame.timestamp_ms
        while frame.timestamp_ms - self._frames[0][0] > self._retention_ms:
            self._frames.popleft()


    def nearest(self, timestamp_ms: int) -> bytes | None:
        """The buffered frame closest to ``timestamp_ms``, or None if none is close enough."""
        if not self._frames:
            return None
        stamp, jpeg = min(self._frames, key=lambda item: abs(item[0] - timestamp_ms))
        return jpeg if abs(stamp - timestamp_ms) <= self._max_gap_ms else None