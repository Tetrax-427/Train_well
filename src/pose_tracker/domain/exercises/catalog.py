from __future__ import annotations

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.exercises.curl import CurlSettings, build_curl
from pose_tracker.domain.exercises.deadlift import DeadliftSettings, build_deadlift
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
) -> dict[str, Exercise]:
    exercises = (
        build_squat(squat),
        build_shoulder_press(shoulder_press),
        build_push_up(push_up),
        build_deadlift(deadlift),
        build_curl(curl),
    )
    return {exercise.key: exercise for exercise in exercises}