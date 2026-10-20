from __future__ import annotations

from operator import attrgetter
import pytest

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import ( 
    ReachBelowRule, StayBelowRule, ReachAboveRule, StayStillRule, StayAboveRule, 
    BandAtRestRule, DriftFromRestRule, MedianBandRule, BandAtPeakRule, TempoRule,)
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample


def make_rep(knees: list[float | None], leans: list[float | None]) -> Rep:
    return Rep(tuple(
        Sample(i * 100, Pose(()), BodyFeatures(k, l))
        for i, (k, l) in enumerate(zip(knees, leans))
    ))


DEPTH = ReachBelowRule("depth", "deeper", attrgetter("knee_angle"), 100)
LEAN = StayBelowRule("lean", "chest up", attrgetter("torso_lean_deg"), 50)


def test_depth_violation_points_at_deepest_moment() -> None:
    violation = DEPTH.evaluate(make_rep([170, 130, 115, 140], [0] * 4))
    assert violation is not None
    assert violation.measured == 115
    assert violation.timestamp_ms == 200
    assert violation.limit == 100


def test_depth_ok_when_target_reached() -> None:
    assert DEPTH.evaluate(make_rep([170, 130, 95, 140], [0] * 4)) is None


def test_lean_violation_points_at_worst_moment() -> None:
    violation = LEAN.evaluate(make_rep([0] * 4, [10, 60, 70, 30]))
    assert violation is not None
    assert violation.measured == 70
    assert violation.timestamp_ms == 200


def test_lean_ok_within_limit() -> None:
    assert LEAN.evaluate(make_rep([0] * 3, [10, 40, 50])) is None


def test_unmeasurable_samples_are_ignored() -> None:
    rep = make_rep([None, None], [None, None])
    assert DEPTH.evaluate(rep) is None
    assert LEAN.evaluate(rep) is None

ABOVE = ReachAboveRule("lockout", "extend", attrgetter("knee_angle"), 165)
STILL = StayStillRule("still", "keep still", attrgetter("knee_angle"), 20)


def test_reach_above_flags_peak_below_target() -> None:
    violation = ABOVE.evaluate(make_rep([120, 150, 160, 140], [0] * 4))
    assert violation is not None
    assert violation.measured == 160
    assert violation.timestamp_ms == 200


def test_reach_above_ok_when_target_reached() -> None:
    assert ABOVE.evaluate(make_rep([120, 170, 140], [0] * 3)) is None


def test_stay_still_flags_spread_and_points_at_biggest_departure() -> None:
    violation = STILL.evaluate(make_rep([170, 165, 120, 168], [0] * 4))
    assert violation is not None
    assert violation.measured == 50
    assert violation.timestamp_ms == 200


def test_stay_still_ok_within_limit_or_with_too_little_data() -> None:
    assert STILL.evaluate(make_rep([170, 165, 160], [0] * 3)) is None
    assert STILL.evaluate(make_rep([170], [0])) is None

FLOOR = StayAboveRule("floor", "keep up", attrgetter("knee_angle"), 160)
BAND = BandAtRestRule("band", "place", attrgetter("torso_lean_deg"), -0.3, 0.3)


def rep_with_lead_in(values: list[float], lead_in: int) -> Rep:
    samples = tuple(
        Sample(i * 100, Pose(()), BodyFeatures(None, v)) for i, v in enumerate(values)
    )
    return Rep(samples, lead_in_count=lead_in)


def test_stay_above_flags_the_lowest_value() -> None:
    violation = FLOOR.evaluate(make_rep([175, 150, 120, 170], [0] * 4))
    assert violation is not None
    assert violation.measured == 120
    assert violation.timestamp_ms == 200


def test_stay_above_ok_when_never_below_limit() -> None:
    assert FLOOR.evaluate(make_rep([175, 165, 170], [0] * 3)) is None


def test_band_ignores_samples_after_the_lead_in() -> None:
    assert BAND.evaluate(rep_with_lead_in([0.0, 0.1, 0.9, 0.9, 0.9], lead_in=2)) is None


def test_band_flags_the_median_when_outside() -> None:
    violation = BAND.evaluate(rep_with_lead_in([0.5, 0.6, 0.7, 0.0], lead_in=3))
    assert violation is not None
    assert violation.measured == 0.6
    assert violation.limit == 0.3


def test_band_falls_back_to_the_first_sample_without_a_lead_in() -> None:
    assert BAND.evaluate(rep_with_lead_in([0.0, 0.9], lead_in=0)) is None

DRIFT_UP = DriftFromRestRule("up", "msg", attrgetter("torso_lean_deg"), limit=10)
DRIFT_DOWN = DriftFromRestRule(
    "down", "msg", attrgetter("torso_lean_deg"), limit=0.1, direction=-1, relative=True
)


def test_drift_flags_an_increase_at_its_worst_moment() -> None:
    violation = DRIFT_UP.evaluate(rep_with_lead_in([40, 40, 45, 55, 48], lead_in=2))
    assert violation is not None
    assert violation.measured == 15
    assert violation.timestamp_ms == 300


def test_drift_ok_within_limit() -> None:
    assert DRIFT_UP.evaluate(rep_with_lead_in([40, 40, 45, 48], lead_in=2)) is None


def test_relative_decrease_is_a_fraction_of_the_baseline() -> None:
    violation = DRIFT_DOWN.evaluate(rep_with_lead_in([50, 50, 48, 40, 45], lead_in=2))
    assert violation is not None
    assert violation.measured == pytest.approx(0.2)
    assert violation.timestamp_ms == 300


def test_drift_uses_the_first_sample_when_there_is_no_lead_in() -> None:
    assert DRIFT_UP.evaluate(rep_with_lead_in([40, 45, 60], lead_in=0)) is not None


def test_drift_rejects_an_invalid_direction() -> None:
    with pytest.raises(ValueError):
        DriftFromRestRule("d", "m", attrgetter("torso_lean_deg"), 1.0, direction=0)

MEDIAN = MedianBandRule("median", "centered", attrgetter("torso_lean_deg"), -0.3, 0.3)


def test_median_band_ignores_a_few_outliers() -> None:
    assert MEDIAN.evaluate(make_rep([0] * 5, [0.0, 0.1, 5.0, -0.1, 0.0])) is None


def test_median_band_flags_a_typical_value_outside_the_band() -> None:
    violation = MEDIAN.evaluate(make_rep([0] * 5, [0.5, 0.6, 0.7, 0.0, 0.8]))
    assert violation is not None
    assert violation.measured == 0.6
    assert violation.limit == 0.3

PEAK = BandAtPeakRule(
    "peak", "msg", attrgetter("torso_lean_deg"), attrgetter("knee_angle"), 0.0, 20.0
)


def test_band_at_peak_checks_the_value_at_the_peak_sample() -> None:
    violation = PEAK.evaluate(make_rep([100, 170, 120], [5, 30, 5]))
    assert violation is not None
    assert (violation.measured, violation.limit, violation.timestamp_ms) == (30, 20, 100)


def test_band_at_peak_ok_when_the_value_is_in_band_or_missing() -> None:
    assert PEAK.evaluate(make_rep([100, 170, 120], [5, 15, 5])) is None
    assert PEAK.evaluate(make_rep([100, 170, 120], [5, None, 5])) is None


def test_tempo_rule_flags_fast_reps() -> None:
    rep = make_rep([0] * 3, [0] * 3)  # lasts 0.2 s
    violation = TempoRule("tempo", "slow down", min_seconds=0.5).evaluate(rep)
    assert violation is not None
    assert (violation.measured, violation.limit) == (pytest.approx(0.2), 0.5)
    assert TempoRule("tempo", "slow down", min_seconds=0.2).evaluate(rep) is None