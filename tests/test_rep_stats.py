from __future__ import annotations

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample


def make_rep(values: list[tuple[float | None, float | None]]) -> Rep:
    return Rep(tuple(
        Sample(i * 100, Pose(()), BodyFeatures(knee, lean))
        for i, (knee, lean) in enumerate(values)
    ))


def test_ranges_cover_only_measurable_features() -> None:
    from pose_tracker.domain.rep_stats import feature_ranges

    ranges = feature_ranges(make_rep([(170, 10), (90, None), (175, 30)]))
    assert ranges == {"knee_angle": (90, 175), "torso_lean_deg": (10, 30)}


def test_ranges_can_be_limited_to_named_features() -> None:
    from pose_tracker.domain.rep_stats import feature_ranges

    ranges = feature_ranges(make_rep([(170, 10), (90, 20)]), ("knee_angle",))
    assert ranges == {"knee_angle": (90, 170)}