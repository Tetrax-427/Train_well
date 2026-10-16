from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import ReachBelowRule, StayBelowRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class SquatSettings:
    """Starting-point thresholds in degrees. Tune against real footage."""

    target_knee_angle: float = 100.0    # at the bottom, knee angle should be <= this
    max_torso_lean_deg: float = 50.0    # trunk angle from vertical should stay <= this
    rest_knee_angle: float = 160.0
    leave_knee_angle: float = 150.0


def build_squat(settings: SquatSettings = SquatSettings()) -> Exercise:
    knee_angle = attrgetter("knee_angle")
    torso_lean = attrgetter("torso_lean_deg")
    return Exercise(
        key="squat",
        name="Squat",
        required_view=CameraView.SIDE,
        driver=knee_angle,
        thresholds=RepThresholds(
            rest_angle=settings.rest_knee_angle, leave_angle=settings.leave_knee_angle
        ),
        rules=(
            ReachBelowRule(
                "squat_depth",
                "Go deeper: lower until your thighs are about parallel",
                knee_angle,
                settings.target_knee_angle,
            ),
            StayBelowRule(
                "torso_lean",
                "Chest up: you are leaning too far forward",
                torso_lean,
                settings.max_torso_lean_deg,
            ),
        ),
        explanations={
            "squat_depth": (
                "A shallow squat uses a smaller range of motion, so your glutes and thighs "
                "get less work than they would from a full-depth rep."
            ),
            "torso_lean": (
                "Leaning far forward shifts the load from your legs onto your lower back, "
                "and usually means your chest dropped as you descended."
            ),
        },
        logged_features=("knee_angle", "torso_lean_deg"),
    )