from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from pose_tracker.domain.form import FormViolation
from pose_tracker.domain.rep import Rep, Sample

_MIN_TRAVEL = 0.2  # torso lengths; shorter paths are too small to judge

Track = list[tuple[Sample, float, float]]  # (sample, hand_x, hand_y)


def _hand_track(samples: Sequence[Sample]) -> Track:
    track: Track = []
    for sample in samples:
        x, y = sample.features.hand_x, sample.features.hand_y
        if x is not None and y is not None:
            track.append((sample, x, y))
    return track


def _max_deviation(segment: Track) -> tuple[float, Sample] | None:
    """Largest distance of any point from the straight line between the segment's ends."""
    _, x0, y0 = segment[0]
    _, x1, y1 = segment[-1]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < _MIN_TRAVEL:
        return None
    return max(
        ((abs(dx * (y - y0) - dy * (x - x0)) / length, sample) for sample, x, y in segment),
        key=lambda item: item[0],
    )


@dataclass(frozen=True, slots=True)
class PathDeviationRule:
    """Violation if the hand strays from a straight line on the way up or down.

    Up-leg: lowest point before the top -> top. Down-leg: top -> end of rep.
    Distances are in torso lengths.
    """

    rule_id: str
    message: str
    limit: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        track = _hand_track(rep.samples)
        if len(track) < 3:
            return None
        top = max(range(len(track)), key=lambda i: track[i][2])
        bottom = min(range(top + 1), key=lambda i: track[i][2])
        found = [
            d for leg in (track[bottom : top + 1], track[top:])
            if (d := _max_deviation(leg)) is not None
        ]
        if not found:
            return None
        deviation, sample = max(found, key=lambda item: item[0])
        if deviation <= self.limit:
            return None
        return FormViolation(
            self.rule_id, self.message, deviation, self.limit, sample.timestamp_ms, sample.pose
        )


@dataclass(frozen=True, slots=True)
class SteadinessRule:
    """Violation if the hand shakes during the rep (the lead-in is ignored).

    Shake = RMS of (hand position - centered moving average over ``window`` frames),
    in torso lengths. Frame-rate dependent: tuned for roughly 30 fps.
    """

    rule_id: str
    message: str
    limit: float
    window: int = 7

    def __post_init__(self) -> None:
        if self.window < 3 or self.window % 2 == 0:
            raise ValueError("window must be an odd number >= 3")

    def evaluate(self, rep: Rep) -> FormViolation | None:
        track = _hand_track(rep.samples[rep.lead_in_count:])
        if len(track) < self.window:
            return None
        half = self.window // 2
        xs = [x for _, x, _ in track]
        ys = [y for _, _, y in track]
        residuals = [
            (
                math.hypot(
                    xs[i] - _window_mean(xs, i, half), ys[i] - _window_mean(ys, i, half)
                ),
                track[i][0],
            )
            for i in range(half, len(track) - half)
        ]
        rms = math.sqrt(sum(r * r for r, _ in residuals) / len(residuals))
        if rms <= self.limit:
            return None
        _, worst = max(residuals, key=lambda item: item[0])
        return FormViolation(
            self.rule_id, self.message, rms, self.limit, worst.timestamp_ms, worst.pose
        )


def _window_mean(values: Sequence[float], center: int, half: int) -> float:
    return sum(values[center - half : center + half + 1]) / (2 * half + 1)