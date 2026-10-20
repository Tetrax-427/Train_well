from __future__ import annotations

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.exercises.angled_bench import (
    DECLINE,
    INCLINE,
    AngledBenchSettings,
    build_decline_press,
    build_incline_press,
)
from pose_tracker.domain.exercises.bench_press import BenchPressSettings, build_bench_press
from pose_tracker.domain.exercises.bent_over_row import BentOverRowSettings, build_bent_over_row
from pose_tracker.domain.exercises.calf_raise import CalfRaiseSettings, build_calf_raise
from pose_tracker.domain.exercises.curl import CurlSettings, build_curl
from pose_tracker.domain.exercises.deadlift import DeadliftSettings, build_deadlift
from pose_tracker.domain.exercises.hip_thrust import HipThrustSettings, build_hip_thrust
from pose_tracker.domain.exercises.lat_pulldown import (
    CLOSE_GRIP,
    WIDE_GRIP,
    LatPulldownSettings,
    build_close_pulldown,
    build_wide_pulldown,
)
from pose_tracker.domain.exercises.lateral_raise import LateralRaiseSettings, build_lateral_raise
from pose_tracker.domain.exercises.plank import PlankSettings, build_plank
from pose_tracker.domain.exercises.push_up import PushUpSettings, build_push_up
from pose_tracker.domain.exercises.shoulder_press import (
    ShoulderPressSettings,
    build_shoulder_press,
)
from pose_tracker.domain.exercises.squat import SquatSettings, build_squat


def build_catalog(
    squat: SquatSettings,
    shoulder_press: ShoulderPressSettings,
    push_up: PushUpSettings,
    deadlift: DeadliftSettings,
    curl: CurlSettings = CurlSettings(),
    bench_press: BenchPressSettings = BenchPressSettings(),
    lateral_raise: LateralRaiseSettings = LateralRaiseSettings(),
    plank: PlankSettings = PlankSettings(),
    incline_press: AngledBenchSettings = INCLINE,
    decline_press: AngledBenchSettings = DECLINE,
    pulldown_wide: LatPulldownSettings = WIDE_GRIP,
    pulldown_close: LatPulldownSettings = CLOSE_GRIP,
    hip_thrust: HipThrustSettings = HipThrustSettings(),
    bent_over_row: BentOverRowSettings = BentOverRowSettings(),
    calf_raise: CalfRaiseSettings = CalfRaiseSettings(),
) -> dict[str, Exercise]:
    """Every exercise, ordered like a routine: legs, push, pull, core."""
    exercises = (
        build_squat(squat),
        build_deadlift(deadlift),
        build_hip_thrust(hip_thrust),
        build_calf_raise(calf_raise),
        build_bench_press(bench_press),
        build_incline_press(incline_press),
        build_decline_press(decline_press),
        build_shoulder_press(shoulder_press),
        build_lateral_raise(lateral_raise),
        build_push_up(push_up),
        build_wide_pulldown(pulldown_wide),
        build_close_pulldown(pulldown_close),
        build_bent_over_row(bent_over_row),
        build_curl(curl),
        build_plank(plank),
    )
    return {exercise.key: exercise for exercise in exercises}