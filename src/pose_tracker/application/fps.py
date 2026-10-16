from __future__ import annotations

import time
from collections.abc import Callable


class FpsMeter:
    """Exponentially smoothed frames-per-second counter."""

    def __init__(
        self,
        smoothing: float = 0.9,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._smoothing = smoothing
        self._clock = clock
        self._last: float | None = None
        self._fps = 0.0

    @property
    def fps(self) -> float:
        return self._fps

    def tick(self) -> None:
        now = self._clock()
        if self._last is not None and now > self._last:
            instant = 1.0 / (now - self._last)
            self._fps = (
                instant
                if self._fps == 0.0
                else self._smoothing * self._fps + (1 - self._smoothing) * instant
            )
        self._last = now