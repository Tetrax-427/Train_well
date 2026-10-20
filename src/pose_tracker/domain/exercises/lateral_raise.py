from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import (
    DriftFromRestRule,
    ReachAboveRule,
    StayAboveRule,
    StayBelowRule,
    StayStillRule,
)
from pose_tracker.domain.motion_rules import SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class LateralRaiseSettings:
    """Front view, both arms. Starting-point thresholds; tune against real footage."""

    min_raise_deg: float = 80.0           # peak upper-arm angle from the torso
    max_raise_deg: float = 105.0          # shoulder height, not above
    max_arm_asymmetry_deg: float = 15.0   # left vs right arm
    min_arm_bend_deg: float = 120.0       # arms stay nearly straight
    max_shrug: float = 0.15               # fractional drop of shoulder-to-ear height
    max_body_sway_deg: float = 8.0        # sideways trunk lean may vary by at most this
    max_unsteadiness: float = 0.03
    rest_raise_deg: float = 30.0          # at/below this the arms are down
    leave_raise_deg: float = 45.0         # above this a raise has started
    lead_in_ms: int = 1000                # resting history kept with each rep (shrug baseline)


def build_lateral_raise(settings: LateralRaiseSettings = LateralRaiseSettings()) -> Exercise:
    s = settings
    raise_angle = attrgetter("arm_raise_deg")
    return Exercise(
        key="lateral_raise",
        name="Lateral Raise",
        required_view=CameraView.FRONT,
        driver=raise_angle,
        thresholds=RepThresholds(rest_angle=s.rest_raise_deg, leave_angle=s.leave_raise_deg),
        rules=(
            ReachAboveRule(
                "raise_height", "Raise your arms to shoulder height", raise_angle, s.min_raise_deg
            ),
            StayBelowRule(
                "raise_too_high", "Stop at shoulder height, don't lift above it",
                raise_angle, s.max_raise_deg,
            ),
            StayBelowRule(
                "arm_symmetry", "Lift both arms evenly",
                attrgetter("arm_asymmetry_deg"), s.max_arm_asymmetry_deg,
            ),
            StayAboveRule(
                "elbow_bend", "Keep your arms nearly straight, only a slight bend",
                attrgetter("arm_bend_deg"), s.min_arm_bend_deg,
            ),
            DriftFromRestRule(
                "shrugging", "Keep your shoulders down, don't shrug",
                attrgetter("shrug_ratio"), s.max_shrug, direction=-1, relative=True,
            ),
            StayStillRule(
                "body_sway", "Don't sway your body to lift the weights",
                attrgetter("trunk_sway_deg"), s.max_body_sway_deg,
            ),
            SteadinessRule(
                "control", "Jerky: lift smoothly and control the weights", s.max_unsteadiness
            ),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=(
            "arm_raise_deg", "arm_asymmetry_deg", "arm_bend_deg", "shrug_ratio", "trunk_sway_deg",
        ),
        position_hint="Face the camera with both arms and your upper body in frame",
        explanations={
            "raise_height": (
                "Stopping short of shoulder height means the side of your shoulders gets "
                "less work through the main part of the movement."
            ),
            "raise_too_high": (
                "Lifting above shoulder height shifts the work to your upper traps and can "
                "pinch the shoulder joint. Stop when your arms are level with the floor."
            ),
            "arm_symmetry": (
                "When one arm lifts higher than the other, one shoulder does more of the "
                "work and the weaker side falls behind."
            ),
            "elbow_bend": (
                "Bending your elbows a lot shortens the lever and turns the raise into a "
                "press or curl, so your shoulders get less work."
            ),
            "shrugging": (
                "Shrugging moves the work from the sides of your shoulders to your upper "
                "traps. Keep your shoulders down and away from your ears."
            ),
            "body_sway": (
                "Swaying to throw the weights up means momentum is doing the lifting. If you "
                "need to sway, the weights are probably too heavy."
            ),
            "control": (
                "A shaky or jerky path means momentum is moving the weights instead of "
                "your shoulders. Lift and lower them smoothly."
            ),
        },
    )