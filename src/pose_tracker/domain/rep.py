from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.pose import Pose


@dataclass(frozen=True, slots=True)
class Sample:
    timestamp_ms: int
    pose: Pose
    features: BodyFeatures


@dataclass(frozen=True, slots=True)
class Rep:
    """Samples of one rep. The first ``lead_in_count`` were recorded at rest, before it began."""

    samples: tuple[Sample, ...]
    lead_in_count: int = 0

    @property
    def start_ms(self) -> int:
        return self.samples[self.lead_in_count].timestamp_ms

    @property
    def end_ms(self) -> int:
        return self.samples[-1].timestamp_ms

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True, slots=True)
class RepThresholds:
    """Hysteresis band around the resting value of the driving angle.

    leave_angle < rest_angle: a rep is a dip below rest (squat: knee bends).
    leave_angle > rest_angle: a rep is a rise above rest (press: elbow extends).
    """

    rest_angle: float
    leave_angle: float

    def __post_init__(self) -> None:
        if self.rest_angle == self.leave_angle:
            raise ValueError("rest_angle and leave_angle must differ (hysteresis gap)")

    @property
    def dips(self) -> bool:
        return self.leave_angle < self.rest_angle

    def is_at_rest(self, value: float) -> bool:
        return value >= self.rest_angle if self.dips else value <= self.rest_angle

    def has_left_rest(self, value: float) -> bool:
        return value < self.leave_angle if self.dips else value > self.leave_angle


class _State(Enum):
    AWAITING_REST = auto()  # must see the rest position before arming
    READY = auto()
    IN_REP = auto()


class RepDetector:
    def __init__(
        self,
        thresholds: RepThresholds,
        min_duration_ms: int = 300,
        lead_in_ms: int = 0,
    ) -> None:
        self._thresholds = thresholds
        self._min_duration_ms = min_duration_ms
        self._lead_in_ms = lead_in_ms
        self._state = _State.AWAITING_REST
        self._samples: list[Sample] = []
        self._lead_in: deque[Sample] = deque()
        self._lead_in_count = 0

    @property
    def in_rep(self) -> bool:
        return self._state is _State.IN_REP

    def update(self, sample: Sample, value: float) -> Rep | None:
        """Feed one frame. Returns the finished Rep on the frame that completes it."""
        t = self._thresholds
        if self._state is _State.AWAITING_REST:
            if t.is_at_rest(value):
                self._state = _State.READY
                self._remember(sample)
            return None

        if self._state is _State.READY:
            if t.has_left_rest(value):
                self._state = _State.IN_REP
                self._lead_in_count = len(self._lead_in)
                self._samples = [*self._lead_in, sample]
                self._lead_in.clear()
            else:
                self._remember(sample)
            return None

        self._samples.append(sample)
        if not t.is_at_rest(value):
            return None
        rep = Rep(tuple(self._samples), self._lead_in_count)
        self._samples, self._lead_in_count = [], 0
        self._state = _State.READY
        self._remember(sample)
        return rep if rep.duration_ms >= self._min_duration_ms else None

    def reset(self) -> None:
        """Discard any in-progress rep and require the rest position again."""
        self._state = _State.AWAITING_REST
        self._samples = []
        self._lead_in.clear()
        self._lead_in_count = 0

    def _remember(self, sample: Sample) -> None:
        if self._lead_in_ms <= 0:
            return
        self._lead_in.append(sample)
        while sample.timestamp_ms - self._lead_in[0].timestamp_ms > self._lead_in_ms:
            self._lead_in.popleft()