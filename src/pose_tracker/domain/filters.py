from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OneEuroConfig:
    """Lower ``min_cutoff`` = smoother when still. Higher ``beta`` = less lag when moving."""

    min_cutoff: float = 1.0
    beta: float = 10.0
    derivative_cutoff: float = 1.0

    def __post_init__(self) -> None:
        if self.min_cutoff <= 0 or self.derivative_cutoff <= 0:
            raise ValueError("Cutoff frequencies must be positive")
        if self.beta < 0:
            raise ValueError("beta must be non-negative")


class OneEuroFilter:
    """Adaptive low-pass filter for a single scalar signal."""

    def __init__(self, config: OneEuroConfig) -> None:
        self._config = config
        self._value: float | None = None
        self._derivative = 0.0
        self._timestamp_s: float | None = None

    def filter(self, value: float, timestamp_s: float) -> float:
        if self._value is None or self._timestamp_s is None:
            self._value, self._timestamp_s = value, timestamp_s
            return value

        dt = timestamp_s - self._timestamp_s
        if dt <= 0:
            return self._value

        raw_derivative = (value - self._value) / dt
        self._derivative = self._lowpass(
            raw_derivative,
            self._derivative,
            self._alpha(self._config.derivative_cutoff, dt),
        )
        cutoff = self._config.min_cutoff + self._config.beta * abs(self._derivative)
        self._value = self._lowpass(value, self._value, self._alpha(cutoff, dt))
        self._timestamp_s = timestamp_s
        return self._value

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    @staticmethod
    def _lowpass(value: float, previous: float, alpha: float) -> float:
        return alpha * value + (1.0 - alpha) * previous