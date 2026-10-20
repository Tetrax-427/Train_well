from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample

Selector = Callable[[BodyFeatures], float | None]


@dataclass(frozen=True, slots=True)
class FormViolation:
    rule_id: str
    message: str
    measured: float
    limit: float
    timestamp_ms: int
    pose: Pose  # snapshot at the worst moment of the rep


class FormRule(Protocol):
    @property
    def rule_id(self) -> str: ...

    def evaluate(self, rep: Rep) -> FormViolation | None: ...

def _scored(rep: Rep, selector: Selector) -> list[tuple[float, Sample]]:
    return [
        (value, sample)
        for sample in rep.samples
        if (value := selector(sample.features)) is not None
    ]


@dataclass(frozen=True, slots=True)
class ReachBelowRule:
    """Violation unless the feature gets down to ``target`` at some point in the rep."""

    rule_id: str
    message: str
    selector: Selector
    target: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        scored = _scored(rep, self.selector)
        if not scored:
            return None
        value, sample = min(scored, key=lambda item: item[0])
        if value <= self.target:
            return None
        return FormViolation(
            self.rule_id, self.message, value, self.target, sample.timestamp_ms, sample.pose
        )


@dataclass(frozen=True, slots=True)
class StayBelowRule:
    """Violation if the feature ever exceeds ``limit`` during the rep."""

    rule_id: str
    message: str
    selector: Selector
    limit: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        scored = _scored(rep, self.selector)
        if not scored:
            return None
        value, sample = max(scored, key=lambda item: item[0])
        if value <= self.limit:
            return None
        return FormViolation(
            self.rule_id, self.message, value, self.limit, sample.timestamp_ms, sample.pose
        )

@dataclass(frozen=True, slots=True)
class ReachAboveRule:
    """Violation unless the feature gets up to ``target`` at some point in the rep."""

    rule_id: str
    message: str
    selector: Selector
    target: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        scored = _scored(rep, self.selector)
        if not scored:
            return None
        value, sample = max(scored, key=lambda item: item[0])
        if value >= self.target:
            return None
        return FormViolation(
            self.rule_id, self.message, value, self.target, sample.timestamp_ms, sample.pose
        )


@dataclass(frozen=True, slots=True)
class StayStillRule:
    """Violation if the feature varies by more than ``limit`` (max - min) during the rep."""

    rule_id: str
    message: str
    selector: Selector
    limit: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        scored = _scored(rep, self.selector)
        if len(scored) < 2:
            return None
        spread = max(v for v, _ in scored) - min(v for v, _ in scored)
        if spread <= self.limit:
            return None
        first = scored[0][0]
        _, sample = max(scored, key=lambda item: abs(item[0] - first))  # biggest departure
        return FormViolation(
            self.rule_id, self.message, spread, self.limit, sample.timestamp_ms, sample.pose
        )

@dataclass(frozen=True, slots=True)
class StayAboveRule:
    """Violation if the feature ever drops below ``limit`` during the rep."""

    rule_id: str
    message: str
    selector: Selector
    limit: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        scored = _scored(rep, self.selector)
        if not scored:
            return None
        value, sample = min(scored, key=lambda item: item[0])
        if value >= self.limit:
            return None
        return FormViolation(
            self.rule_id, self.message, value, self.limit, sample.timestamp_ms, sample.pose
        )


@dataclass(frozen=True, slots=True)
class BandAtRestRule:
    """Violation unless the feature sits inside [low, high] in the resting position.

    Uses the median over the lead-in samples (the first sample if there are none).
    """

    rule_id: str
    message: str
    selector: Selector
    low: float
    high: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        resting = Rep(rep.samples[: max(rep.lead_in_count, 1)])
        scored = sorted(_scored(resting, self.selector), key=lambda item: item[0])
        if not scored:
            return None
        value, sample = scored[len(scored) // 2]
        if self.low <= value <= self.high:
            return None
        limit = self.low if value < self.low else self.high
        return FormViolation(
            self.rule_id, self.message, value, limit, sample.timestamp_ms, sample.pose
        )

@dataclass(frozen=True, slots=True)
class DriftFromRestRule:
    """Violation if the feature drifts from its resting baseline by more than ``limit``.

    Baseline = median over the lead-in samples (the first sample if there are none).
    ``direction`` +1 flags increases, -1 flags decreases. With ``relative`` the drift
    is a fraction of the baseline instead of absolute units.
    """

    rule_id: str
    message: str
    selector: Selector
    limit: float
    direction: int = 1
    relative: bool = False

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise ValueError("direction must be +1 or -1")

    def evaluate(self, rep: Rep) -> FormViolation | None:
        resting = _scored(Rep(rep.samples[: max(rep.lead_in_count, 1)]), self.selector)
        active = _scored(Rep(rep.samples[rep.lead_in_count :]), self.selector)
        if not resting or not active:
            return None
        baseline = sorted(value for value, _ in resting)[len(resting) // 2]
        if self.relative and baseline == 0.0:
            return None

        def drift(value: float) -> float:
            change = self.direction * (value - baseline)
            return change / abs(baseline) if self.relative else change

        measured, sample = max(
            ((drift(value), s) for value, s in active), key=lambda item: item[0]
        )
        if measured <= self.limit:
            return None
        return FormViolation(
            self.rule_id, self.message, measured, self.limit, sample.timestamp_ms, sample.pose
        )

@dataclass(frozen=True, slots=True)
class MedianBandRule:
    """Violation unless the typical (median) value over the whole rep sits inside [low, high]."""

    rule_id: str
    message: str
    selector: Selector
    low: float
    high: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        scored = sorted(_scored(rep, self.selector), key=lambda item: item[0])
        if not scored:
            return None
        value, sample = scored[len(scored) // 2]
        if self.low <= value <= self.high:
            return None
        limit = self.low if value < self.low else self.high
        return FormViolation(
            self.rule_id, self.message, value, limit, sample.timestamp_ms, sample.pose
        )

@dataclass(frozen=True, slots=True)
class BandAtPeakRule:
    """Violation unless ``selector`` sits inside [low, high] at the rep's peak.

    The peak is the sample where ``peak`` is largest (for example the top of a hip thrust,
    where the hip angle is greatest).
    """

    rule_id: str
    message: str
    selector: Selector
    peak: Selector
    low: float
    high: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        peaks = _scored(rep, self.peak)
        if not peaks:
            return None
        _, sample = max(peaks, key=lambda item: item[0])
        value = self.selector(sample.features)
        if value is None or self.low <= value <= self.high:
            return None
        limit = self.low if value < self.low else self.high
        return FormViolation(
            self.rule_id, self.message, value, limit, sample.timestamp_ms, sample.pose
        )


@dataclass(frozen=True, slots=True)
class TempoRule:
    """Violation if the rep is faster than ``min_seconds`` (bouncing or dropping the weight)."""

    rule_id: str
    message: str
    min_seconds: float

    def evaluate(self, rep: Rep) -> FormViolation | None:
        seconds = rep.duration_ms / 1000
        if seconds >= self.min_seconds:
            return None
        sample = rep.samples[len(rep.samples) // 2]
        return FormViolation(
            self.rule_id, self.message, seconds, self.min_seconds,
            sample.timestamp_ms, sample.pose,
        )