from __future__ import annotations

import pytest

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, RepDetector, RepThresholds, Sample

THRESHOLDS = RepThresholds(rest_angle=160, leave_angle=150)
ONE_REP = [170, 170, 170, 140, 120, 100, 90, 100, 120, 140, 155, 165]


def feed(detector: RepDetector, values: list[float], step_ms: int = 100) -> list[Rep]:
    reps = []
    for i, value in enumerate(values):
        sample = Sample(i * step_ms, Pose(()), BodyFeatures(value, None))
        rep = detector.update(sample, value)
        if rep is not None:
            reps.append(rep)
    return reps


def test_counts_a_full_rep() -> None:
    assert len(feed(RepDetector(THRESHOLDS), ONE_REP)) == 1


def test_dips_that_stay_above_leave_angle_are_ignored() -> None:
    assert feed(RepDetector(THRESHOLDS), [170, 155, 158, 152, 170, 155, 170]) == []


def test_partial_return_inside_hysteresis_band_is_one_rep() -> None:
    assert len(feed(RepDetector(THRESHOLDS), [170, 140, 155, 140, 165])) == 1


def test_must_see_rest_position_before_counting() -> None:
    detector = RepDetector(THRESHOLDS)
    assert feed(detector, [100, 110, 130, 165]) == []
    assert len(feed(detector, ONE_REP[3:])) == 1


def test_too_short_rep_is_discarded() -> None:
    assert feed(RepDetector(THRESHOLDS), ONE_REP, step_ms=10) == []


def test_reset_discards_in_progress_rep() -> None:
    detector = RepDetector(THRESHOLDS)
    feed(detector, [170, 140, 120])
    assert detector.in_rep
    detector.reset()
    assert not detector.in_rep
    assert feed(detector, [165, 170]) == []

RISE = RepThresholds(rest_angle=125, leave_angle=140)
PRESS = [100, 100, 100, 130, 150, 170, 170, 150, 130, 110, 100]


def test_equal_thresholds_rejected() -> None:
    with pytest.raises(ValueError):
        RepThresholds(rest_angle=150, leave_angle=150)


def test_rising_exercise_counts_a_rep() -> None:
    assert len(feed(RepDetector(RISE), PRESS)) == 1


def test_rising_exercise_ignores_small_movements_at_rest() -> None:
    assert feed(RepDetector(RISE), [100, 110, 120, 105, 130, 100]) == []


def test_lead_in_keeps_the_bottom_before_the_rep_without_counting_it_in_duration() -> None:
    [rep] = feed(RepDetector(RISE, lead_in_ms=1500), PRESS)
    assert rep.lead_in_count == 4
    assert len(rep.samples) == 10
    assert rep.start_ms == 400
    assert rep.duration_ms == 500
    assert min(s.features.knee_angle for s in rep.samples) == 100  # bottom before the press


def test_lead_in_is_limited_to_its_window() -> None:
    [rep] = feed(RepDetector(RISE, lead_in_ms=250), PRESS)
    assert rep.lead_in_count == 3

def test_elapsed_time_of_the_running_rep() -> None:
    detector = RepDetector(THRESHOLDS)
    assert detector.elapsed_ms is None
    feed(detector, [170, 140, 120])  # the rep starts at 100 ms and the last sample is at 200 ms
    assert detector.elapsed_ms == 100