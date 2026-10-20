from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import ReachAboveRule, StayAboveRule, StayStillRule, TempoRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class CalfRaiseSettings:
    """Standing calf raise, side view. Starting-point thresholds; tune against real footage.

    The foot angle is the heel-to-toe line against horizontal, so it only changes when the
    heel lifts. Heel and toe are noisy landmarks: calibrate the height first.
    """

    min_raise_deg: float = 18.0           # at the top the heel should rise to >= this
    min_knee_angle: float = 165.0         # legs stay straight
    max_torso_change_deg: float = 8.0     # the torso may move by at most this during a rep
    min_rep_seconds: float = 1.0          # faster reps count as bouncing
    rest_foot_angle: float = 8.0          # at/below this your heels are down
    leave_foot_angle: float = 14.0        # above this a raise has started


def build_calf_raise(settings: CalfRaiseSettings = CalfRaiseSettings()) -> Exercise:
    s = settings
    return Exercise(
        key="calf_raise",
        name="Calf Raise",
        required_view=CameraView.SIDE,
        driver=attrgetter("foot_angle_deg"),
        thresholds=RepThresholds(rest_angle=s.rest_foot_angle, leave_angle=s.leave_foot_angle),
        rules=(
            ReachAboveRule(
                "calf_height", "Rise higher: push all the way up onto your toes",
                attrgetter("foot_angle_deg"), s.min_raise_deg,
            ),
            StayAboveRule(
                "knee_bend", "Keep your legs straight",
                attrgetter("knee_angle"), s.min_knee_angle,
            ),
            StayStillRule(
                "torso_swing", "Stay tall: don't lean to lift the weight",
                attrgetter("torso_lean_deg"), s.max_torso_change_deg,
            ),
            TempoRule(
                "calf_tempo", "Too fast: pause at the top and lower with control",
                s.min_rep_seconds,
            ),
        ),
        logged_features=("foot_angle_deg", "knee_angle", "torso_lean_deg"),
        position_hint="Stand side-on to the camera, whole body in frame, feet visible",
        explanations={
            "calf_height": (
                "Stopping short of full height leaves the top of the movement untrained, "
                "so your calves work through a smaller range."
            ),
            "knee_bend": (
                "Bending your knees brings your thighs into the movement and takes work "
                "off your calves. Keep your legs straight with a soft lock."
            ),
            "torso_swing": (
                "Leaning back and forth to bounce the weight up uses momentum instead of "
                "your calves. Stay upright and move only at the ankles."
            ),
            "calf_tempo": (
                "Fast, bouncing reps use the spring of your Achilles tendon instead of "
                "muscle. Pause briefly at the top and lower slowly."
            ),
        },
    )