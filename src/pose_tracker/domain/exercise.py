from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import FormRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class Exercise:
    """Declarative definition: what to measure, when a rep happens, what counts as bad form."""

    key: str
    name: str
    required_view: CameraView
    driver: Callable[[BodyFeatures], float | None]  # the angle that defines a rep
    thresholds: RepThresholds
    rules: tuple[FormRule, ...]
    lead_in_ms: int = 0  # resting history kept with each rep (needed when the bottom precedes the rep)
    logged_features: tuple[str, ...] | None = None  # features written to logs; None = all
    position_hint: str = "Keep your whole body in frame"  # shown when the driver can't be measured
    explanations: Mapping[str, str] = field(default_factory=dict)  # rule_id -> why it matters