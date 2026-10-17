from __future__ import annotations

import argparse
import logging
from contextlib import ExitStack, closing

from pose_tracker.application.composite_recorder import CompositeRepRecorder
from pose_tracker.application.derived_landmarks_estimator import DerivedLandmarksEstimator
from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.application.exercise_hud import ExerciseHudAnalyzer
from pose_tracker.application.fps import FpsMeter
from pose_tracker.application.frame_buffer import FrameBuffer
from pose_tracker.application.history_recorder import HistoryRepRecorder
from pose_tracker.application.pipeline import PosePipeline
from pose_tracker.application.smoothed_estimator import SmoothedPoseEstimator
from pose_tracker.config import AppConfig
from pose_tracker.domain.exercises.catalog import build_catalog
from pose_tracker.domain.pose_smoother import PoseSmoother
from pose_tracker.domain.view import StableViewDetector, ViewDetector
from pose_tracker.errors import PoseTrackerError
from pose_tracker.infrastructure.filesystem_snapshot_store import FileSnapshotStore
from pose_tracker.infrastructure.mediapipe_estimator import MediaPipePoseEstimator
from pose_tracker.infrastructure.opencv_camera import OpenCvCamera
from pose_tracker.infrastructure.opencv_display import OpenCvDisplay
from pose_tracker.infrastructure.opencv_frame_encoder import OpenCvJpegEncoder
from pose_tracker.infrastructure.opencv_renderer import OpenCvPoseRenderer
from pose_tracker.infrastructure.sqlite_session_repository import SqliteSessionRepository
from pose_tracker.infrastructure.text_rep_recorder import TextFileRepRecorder


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    config = AppConfig()
    catalog = build_catalog(
        config.squat, config.shoulder_press, config.push_up, config.deadlift, config.curl
    )
    parser = argparse.ArgumentParser(description="Gym form tracker")
    parser.add_argument("--exercise", choices=sorted(catalog), default="squat")
    exercise = catalog[parser.parse_args().exercise]

    try:
        with ExitStack() as stack:
            camera = stack.enter_context(closing(OpenCvCamera(
                config.camera_index, config.frame_width,
                config.frame_height, config.mirror,
            )))
            base_estimator = stack.enter_context(closing(MediaPipePoseEstimator(
                config.model_path, config.min_detection_confidence,
                config.min_presence_confidence, config.min_tracking_confidence,
            )))
            smoothed_estimator = SmoothedPoseEstimator(
                base_estimator, PoseSmoother(config.smoothing)
            )
            estimator = DerivedLandmarksEstimator(smoothed_estimator)
            display = stack.enter_context(closing(OpenCvDisplay(config.window_name)))

            frame_buffer = FrameBuffer(
                OpenCvJpegEncoder(config.snapshot_max_width, config.snapshot_quality),
                config.snapshot_retention_ms,
            )
            repository = stack.enter_context(closing(SqliteSessionRepository(
                config.history_dir / "history.db",
                FileSnapshotStore(config.history_dir / "snapshots"),
            )))
            # Entered after the repository, so they close first on exit.
            text_recorder = stack.enter_context(
                closing(TextFileRepRecorder(config.sessions_dir))
            )
            history_recorder = stack.enter_context(
                closing(HistoryRepRecorder(repository, frame_buffer))
            )

            analyzer = ExerciseHudAnalyzer(
                ExerciseAnalyzer(
                    exercise,
                    StableViewDetector(ViewDetector(config.view_thresholds)),
                    config.visibility_threshold,
                    CompositeRepRecorder(text_recorder, history_recorder),
                )
            )
            PosePipeline(
                source=camera,
                estimator=estimator,
                analyzer=analyzer,
                renderer=OpenCvPoseRenderer(config.visibility_threshold),
                display=display,
                fps_meter=FpsMeter(),
                observers=(frame_buffer,),
            ).run()
    except PoseTrackerError:
        logging.getLogger(__name__).exception("Fatal application error")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())