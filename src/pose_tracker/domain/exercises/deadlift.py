from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import (
    BandAtRestRule,
    DriftFromRestRule,
    ReachAboveRule,
    StayAboveRule,
    StayBelowRule,
)
from pose_tracker.domain.motion_rules import SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class DeadliftSettings:
    """Conventional deadlift, side view. Starting-point thresholds; tune against real footage."""

    max_start_torso_deg: float = 70.0     # torso from vertical at setup
    max_torso_drift_deg: float = 10.0     # torso may flatten by at most this during the pull
    max_chord_shrink: float = 0.08        # shoulder-hip chord ratio may drop by at most 8%
    max_layback_deg: float = 5.0          # backward lean past vertical at the top
    min_neck_angle: float = 150.0         # ear-shoulder-hip
    lockout_hip_angle: float = 170.0
    lockout_knee_angle: float = 170.0
    min_elbow_angle: float = 160.0        # arms stay straight
    max_bar_start_offset: float = 0.15    # wrist vs mid-foot at setup, either way
    max_bar_forward_drift: float = 0.2    # wrist ahead of mid-foot during the lift
    min_start_knee_angle: float = 100.0   # lower than this at setup = squatting the lift
    max_unsteadiness: float = 0.015
    rest_hip_angle: float = 110.0         # at/below this you are in the bottom position
    leave_hip_angle: float = 125.0        # above this the pull has started
    lead_in_ms: int = 1500                # setup history kept with each rep


def build_deadlift(settings: DeadliftSettings = DeadliftSettings()) -> Exercise:
    torso_lean = attrgetter("torso_lean_deg")
    knee = attrgetter("knee_angle")
    bar = attrgetter("bar_offset")
    s = settings
    return Exercise(
        key="deadlift",
        name="Deadlift",
        required_view=CameraView.SIDE,
        driver=attrgetter("hip_angle"),
        thresholds=RepThresholds(rest_angle=s.rest_hip_angle, leave_angle=s.leave_hip_angle),
        rules=(
            BandAtRestRule(
                "start_back", "Too bent over at the start: raise your chest, lower your hips",
                torso_lean, 0.0, s.max_start_torso_deg,
            ),
            DriftFromRestRule(
                "hips_shoot_up", "Hips rising too early: lift hips and chest together",
                torso_lean, s.max_torso_drift_deg,
            ),
            DriftFromRestRule(
                "back_rounding", "Possible back rounding: chest up, keep your spine neutral",
                attrgetter("torso_thigh_ratio"), s.max_chord_shrink, direction=-1, relative=True,
            ),
            StayBelowRule(
                "lockout_arch", "Don't lean back at the top: stand tall",
                attrgetter("torso_layback_deg"), s.max_layback_deg,
            ),
            StayAboveRule(
                "head_position", "Keep your neck in line with your spine",
                attrgetter("neck_angle"), s.min_neck_angle,
            ),
            ReachAboveRule(
                "hip_extension", "Drive your hips all the way through at the top",
                attrgetter("hip_angle"), s.lockout_hip_angle,
            ),
            ReachAboveRule(
                "knee_lockout", "Straighten your knees at the top", knee, s.lockout_knee_angle,
            ),
            StayAboveRule(
                "arms_straight", "Keep your arms straight, don't curl the bar",
                attrgetter("elbow_angle"), s.min_elbow_angle,
            ),
            BandAtRestRule(
                "bar_start", "Start with the bar over your mid-foot",
                bar, -s.max_bar_start_offset, s.max_bar_start_offset,
            ),
            StayBelowRule(
                "bar_forward", "Keep the bar close, it drifted away from your legs",
                bar, s.max_bar_forward_drift,
            ),
            BandAtRestRule(
                "start_knees", "Hips too low: this is a deadlift, not a squat",
                knee, s.min_start_knee_angle, 180.0,
            ),
            SteadinessRule(
                "control", "Jerky pull: keep it smooth and controlled", s.max_unsteadiness
            ),
        ),
        explanations={
            "start_back": (
                "Starting with your torso too close to horizontal puts your lower back in a "
                "weak position before the bar has left the floor. Raise your chest and "
                "lower your hips."
            ),
            "hips_shoot_up": (
                "When your hips rise faster than your chest, the lift turns into a stiff-leg "
                "pull and your lower back takes load your legs should share."
            ),
            "back_rounding": (
                "Your shoulder-to-hip distance shrank during the pull, which suggests your "
                "spine curled forward. A rounded back under load stresses the spinal discs. "
                "This is an estimate from the camera, not a spine measurement."
            ),
            "lockout_arch": (
                "Leaning back past vertical at the top compresses your lower back. Finish "
                "tall by squeezing your glutes; the lift ends when you stand straight."
            ),
            "head_position": (
                "A tucked or craned neck breaks the line of your spine. Look at a spot a "
                "few feet ahead on the floor to keep it neutral."
            ),
            "hip_extension": (
                "If your hips don't reach full extension at the top, the rep isn't finished "
                "and your glutes haven't completed their work."
            ),
            "knee_lockout": (
                "Straightening the knees completes the lift. Bent knees at the top mean you "
                "stopped short of standing fully upright."
            ),
            "arms_straight": (
                "Your arms are hooks, not engines. Bending your elbows turns the pull into a "
                "curl and can strain the biceps."
            ),
            "bar_start": (
                "The bar should start over your mid-foot. Starting too far ahead or behind "
                "makes it travel in a curve and harder to balance."
            ),
            "bar_forward": (
                "A bar drifting away from your legs increases the leverage working against "
                "your lower back. Keep it close to your shins and thighs."
            ),
            "start_knees": (
                "Setting your hips too low turns the pull into a squat. Start with hips "
                "higher so your back and hamstrings share the work."
            ),
            "control": (
                "A jerky pull means you're yanking the bar instead of building tension "
                "first. Take the slack out of the bar and pull smoothly."
            ),
        },
        lead_in_ms=s.lead_in_ms,
        logged_features=(
            "hip_angle", "knee_angle", "torso_lean_deg", "torso_thigh_ratio",
            "neck_angle", "elbow_angle", "bar_offset",
        ),
        position_hint="Stand side-on with your hands and feet in frame",
    )