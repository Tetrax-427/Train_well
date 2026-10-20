from __future__ import annotations

from pose_tracker.config import AppConfig
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.exercises.catalog import build_catalog


def catalog_for(config: AppConfig) -> dict[str, Exercise]:
    """Every exercise, built from the thresholds in the app configuration."""
    return build_catalog(
        config.squat, config.shoulder_press, config.push_up, config.deadlift, config.curl,
        config.bench_press, config.lateral_raise, config.plank,
        incline_press=config.incline_press, decline_press=config.decline_press,
        pulldown_wide=config.pulldown_wide, pulldown_close=config.pulldown_close,
        hip_thrust=config.hip_thrust, bent_over_row=config.bent_over_row,
        calf_raise=config.calf_raise,
    )