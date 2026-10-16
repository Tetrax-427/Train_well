from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import ReachAboveRule, ReachBelowRule, StayBelowRule, StayStillRule
from pose_tracker.domain.motion_rules import PathDeviationRule, SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class ShoulderPressSettings:
    """Starting-point thresholds. Tune against real footage."""

    bottom_elbow_angle: float = 100.0    # elbow should bend to <= this at the bottom
    lockout_elbow_angle: float = 165.0   # elbow should extend to >= this at the top
    max_layback_deg: float = 15.0        # backward trunk lean should stay <= this
    max_path_deviation: float = 0.15     # hand vs straight line, in torso lengths
    max_unsteadiness: float = 0.015      # hand shake (RMS), in torso lengths
    max_leg_movement_deg: float = 20.0   # knee angle may change by at most this
    rest_elbow_angle: float = 125.0      # at/below this you are in the bottom position
    leave_elbow_angle: float = 140.0     # above this a press has started
    lead_in_ms: int = 1500               # bottom-position history kept with each rep


def build_shoulder_press(settings: ShoulderPressSettings = ShoulderPressSettings()) -> Exercise:
    elbow = attrgetter("elbow_angle")
    layback = attrgetter("torso_layback_deg")
    knee = attrgetter("knee_angle")
    return Exercise(
        key="shoulder_press",
        name="Shoulder Press",
        required_view=CameraView.SIDE,
        driver=elbow,
        thresholds=RepThresholds(
            rest_angle=settings.rest_elbow_angle, leave_angle=settings.leave_elbow_angle
        ),
        rules=(
            ReachBelowRule(
                "press_bottom", "Lower the weight to shoulder level",
                elbow, settings.bottom_elbow_angle,
            ),
            ReachAboveRule(
                "press_lockout", "Press all the way up, lock out",
                elbow, settings.lockout_elbow_angle,
            ),
            StayBelowRule(
                "layback", "Don't lean back, stay tall",
                layback, settings.max_layback_deg,
            ),
            PathDeviationRule(
                "bar_path", "Keep the press path straight", settings.max_path_deviation
            ),
            SteadinessRule(
                "control", "Unsteady: slow down, control it", settings.max_unsteadiness
            ),
            StayStillRule(
                "leg_drive", "Keep your legs still", knee, settings.max_leg_movement_deg
            ),
        ),
        explanations={
            "press_bottom": (
                "If the weight doesn't come down to about shoulder level, every rep covers "
                "less range of motion and your shoulders get less work."
            ),
            "press_lockout": (
                "Stopping short of full extension leaves the top of the press untrained and "
                "never gets the weight stacked stably over your shoulders."
            ),
            "layback": (
                "Leaning back turns the lift into a partial incline press: your chest takes "
                "over from the shoulders and your lower back arches under load."
            ),
            "bar_path": (
                "The weight should travel in a near-vertical line. Drifting forward or back "
                "makes it harder to control and adds strain to the shoulder joint."
            ),
            "control": (
                "A shaky or jerky path means the weight is moving you rather than you moving "
                "it, which often signals the load is too heavy or the tempo too fast."
            ),
            "leg_drive": (
                "Using your legs to launch the weight turns a strict press into a push press, "
                "so your shoulders do less of the work."
            ),
        },
        lead_in_ms=settings.lead_in_ms,
        logged_features=("elbow_angle", "torso_layback_deg", "knee_angle"),
    )