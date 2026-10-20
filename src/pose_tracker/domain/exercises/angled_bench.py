from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import ReachAboveRule, ReachBelowRule, StayAboveRule, StayStillRule
from pose_tracker.domain.motion_rules import PathDeviationRule, SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class AngledBenchSettings:
    """Incline or decline press, side view. Starting-point thresholds; tune against real footage.

    The shoulder-hip line is measured against horizontal: negative means the shoulders are
    above the hips (incline), positive means below (decline). Reps only count while it lies
    between the two bounds, so standing up or lying flat never counts.
    """

    min_back_tilt_deg: float
    max_back_tilt_deg: float
    bottom_elbow_angle: float = 95.0
    lockout_elbow_angle: float = 165.0
    max_back_shift_deg: float = 10.0     # back angle may change by at most this during a rep
    min_neck_angle: float = 145.0        # ear-shoulder-hip
    max_path_deviation: float = 0.15     # hand vs straight line, in torso lengths
    max_hand_drift: float = 0.30         # horizontal travel of the hand, in torso lengths
    max_unsteadiness: float = 0.03       # hand shake (RMS), in torso lengths
    rest_elbow_angle: float = 155.0      # at/above this you are at the top
    leave_elbow_angle: float = 140.0     # below this the descent has started
    lead_in_ms: int = 1500


INCLINE = AngledBenchSettings(min_back_tilt_deg=-65.0, max_back_tilt_deg=-15.0)
DECLINE = AngledBenchSettings(min_back_tilt_deg=8.0, max_back_tilt_deg=45.0)


def _explanations(focus: str) -> dict[str, str]:
    return {
        "bench_depth": (
            f"Stopping above chest level shortens the range of motion, so your {focus} get "
            "less work. Lower the weight until it reaches your chest."
        ),
        "bench_lockout": (
            "Pressing short of full extension leaves the finish of the movement untrained "
            "and never stacks the weight over your shoulders."
        ),
        "bench_angle": (
            "Your back angle changed during the rep, which means your hips or shoulders "
            "slid on the bench. Keep your upper back and hips planted so the pressing "
            "muscles do the work and your lower back stays supported."
        ),
        "bar_path": (
            "The weight should travel in a smooth, straight line. A wavering path wastes "
            "energy and puts uneven stress on your shoulders."
        ),
        "bar_drift": (
            "Pressing forward or back instead of straight up and down means the weight "
            "isn't stacked over your shoulders, so it is harder to control and strains "
            "the shoulder joint."
        ),
        "control": (
            "A shaky path means the weight is moving you rather than you moving it, which "
            "often signals the load is too heavy or the tempo too fast."
        ),
        "head_position": (
            "Lifting your head off the bench pulls your neck out of line with your spine "
            "and strains it. Keep the back of your head resting on the bench."
        ),
    }


def _build(
    key: str, name: str, s: AngledBenchSettings, chest_part: str, focus: str, setup_hint: str
) -> Exercise:
    elbow = attrgetter("elbow_angle")

    def pressing_elbow_angle(features: BodyFeatures) -> float | None:
        """Drives rep counting, but only while you are lying at the bench angle."""
        tilt = features.back_tilt_deg
        if tilt is None or not s.min_back_tilt_deg <= tilt <= s.max_back_tilt_deg:
            return None
        return features.elbow_angle

    return Exercise(
        key=key,
        name=name,
        required_view=CameraView.SIDE,
        driver=pressing_elbow_angle,
        thresholds=RepThresholds(rest_angle=s.rest_elbow_angle, leave_angle=s.leave_elbow_angle),
        rules=(
            ReachBelowRule(
                "bench_depth", f"Lower the weight to your {chest_part}", elbow, s.bottom_elbow_angle
            ),
            ReachAboveRule(
                "bench_lockout", "Press all the way up, lock out your arms",
                elbow, s.lockout_elbow_angle,
            ),
            StayStillRule(
                "bench_angle", "Keep your back and hips planted on the bench",
                attrgetter("back_tilt_deg"), s.max_back_shift_deg,
            ),
            PathDeviationRule(
                "bar_path", "Keep the press path straight", s.max_path_deviation, inverted=True
            ),
            StayStillRule(
                "bar_drift", "Press straight up and down, not forward or back",
                attrgetter("hand_x"), s.max_hand_drift,
            ),
            SteadinessRule("control", "Unsteady: slow down, control the weight", s.max_unsteadiness),
            StayAboveRule(
                "head_position", "Keep your head resting back on the bench",
                attrgetter("neck_angle"), s.min_neck_angle,
            ),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=("elbow_angle", "back_tilt_deg", "neck_angle", "hand_x"),
        position_hint=setup_hint,
        explanations=_explanations(focus),
    )


def build_incline_press(settings: AngledBenchSettings = INCLINE) -> Exercise:
    return _build(
        "incline_press", "Incline Bench Press", settings,
        chest_part="upper chest",
        focus="upper chest and front shoulders",
        setup_hint="Lie on the incline bench, side-on to the camera, whole body in frame",
    )


def build_decline_press(settings: AngledBenchSettings = DECLINE) -> Exercise:
    return _build(
        "decline_press", "Decline Bench Press", settings,
        chest_part="lower chest",
        focus="lower chest",
        setup_hint="Lie on the decline bench, side-on to the camera, whole body in frame",
    )