from __future__ import annotations

import dataclasses

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.rep import Rep


def feature_ranges(
    rep: Rep, names: tuple[str, ...] | None = None
) -> dict[str, tuple[float, float]]:
    """(min, max) of each measurable feature over the rep. ``None`` selects every feature."""
    selected = names or tuple(f.name for f in dataclasses.fields(BodyFeatures))
    ranges: dict[str, tuple[float, float]] = {}
    for name in selected:
        values = [
            value
            for sample in rep.samples
            if (value := getattr(sample.features, name)) is not None
        ]
        if values:
            ranges[name] = (min(values), max(values))
    return ranges