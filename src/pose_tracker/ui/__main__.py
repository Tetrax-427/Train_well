from __future__ import annotations

import logging
import sys
from contextlib import ExitStack, closing

from PySide6.QtWidgets import QApplication, QMessageBox

from pose_tracker.application.calibration import calibrate, summarize
from pose_tracker.application.composite_recorder import SessionRepRecorder
from pose_tracker.application.derived_landmarks_estimator import DerivedLandmarksEstimator
from pose_tracker.application.frame_buffer import FrameBuffer
from pose_tracker.application.geometric_reference import GeometricReferenceProvider
from pose_tracker.application.history_presenter import HistoryPresenter
from pose_tracker.application.history_recorder import HistoryRepRecorder
from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.application.session_controller import SessionController
from pose_tracker.application.smoothed_estimator import SmoothedPoseEstimator
from pose_tracker.application.training_presenter import TrainingPresenter
from pose_tracker.config import AppConfig
from pose_tracker.domain.pose_smoother import PoseSmoother
from pose_tracker.domain.view import StableViewDetector, ViewDetector
from pose_tracker.errors import CalibrationError, PoseTrackerError
from pose_tracker.infrastructure.calibration_file import read_calibration_file
from pose_tracker.infrastructure.filesystem_snapshot_store import FileSnapshotStore
from pose_tracker.infrastructure.mediapipe_estimator import MediaPipePoseEstimator
from pose_tracker.infrastructure.opencv_camera import OpenCvCamera
from pose_tracker.infrastructure.opencv_frame_encoder import OpenCvJpegEncoder
from pose_tracker.infrastructure.opencv_renderer import OpenCvPoseRenderer
from pose_tracker.infrastructure.opencv_snapshot_painter import OpenCvSnapshotPainter
from pose_tracker.infrastructure.sqlite_session_repository import SqliteSessionRepository
from pose_tracker.infrastructure.text_rep_recorder import TextFileRepRecorder
from pose_tracker.ui.capture_thread import CaptureThread
from pose_tracker.ui.history_view import HistoryView
from pose_tracker.ui.main_window import MainWindow
from pose_tracker.ui.progress_view import ProgressView
from pose_tracker.ui.theme import STYLE_SHEET
from pose_tracker.ui.train_view import TrainView

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)

    base = AppConfig()
    try:
        calibration = calibrate(
            base, read_calibration_file(base.calibration_file), base.calibration_file
        )
    except CalibrationError as exc:
        logger.error("%s", exc)
        QMessageBox.critical(None, base.window_name, str(exc))
        return 1
    config, catalog = calibration.config, calibration.catalog
    logger.info("Calibration (%s): %s", base.calibration_file, summarize(base, calibration))

    try:
        with ExitStack() as stack:
            camera = stack.enter_context(closing(OpenCvCamera(
                config.camera_index, config.frame_width, config.frame_height, config.mirror,
            )))
            base_estimator = stack.enter_context(closing(MediaPipePoseEstimator(
                config.model_path, config.min_detection_confidence,
                config.min_presence_confidence, config.min_tracking_confidence,
            )))
            estimator = DerivedLandmarksEstimator(
                SmoothedPoseEstimator(base_estimator, PoseSmoother(config.smoothing))
            )

            frame_buffer = FrameBuffer(
                OpenCvJpegEncoder(config.snapshot_max_width, config.snapshot_quality),
                config.snapshot_retention_ms,
                min_interval_ms=config.snapshot_min_interval_ms,
            )
            repository = stack.enter_context(closing(SqliteSessionRepository(
                config.history_dir / "history.db",
                FileSnapshotStore(config.history_dir / "snapshots"),
            )))

            def new_recorder() -> SessionRepRecorder:
                return SessionRepRecorder(
                    HistoryRepRecorder(repository, frame_buffer),
                    TextFileRepRecorder(config.sessions_dir),
                )

            controller = SessionController(
                catalog,
                view_detector_factory=lambda: StableViewDetector(
                    ViewDetector(config.view_thresholds)
                ),
                recorder_factory=new_recorder,
                min_visibility=config.visibility_threshold,
            )
            names = {exercise.key: exercise.name for exercise in catalog.values()}
            progress = ProgressPresenter(repository, repository, names)
            presenter = TrainingPresenter(
                controller,
                frame_buffer,
                OpenCvPoseRenderer(config.visibility_threshold, show_fps=False),
                last_time=progress.last_time,
            )
            history_view = HistoryView(
                HistoryPresenter(repository, names, GeometricReferenceProvider()),
                OpenCvSnapshotPainter(config.visibility_threshold),
                progress,
            )
            window = MainWindow(
                config.window_name,
                TrainView(presenter, CaptureThread(camera, estimator), progress),
                history_view,
                ProgressView(progress),
            )
            window.show()
            window.start_capture()
            return app.exec()
    except PoseTrackerError as exc:
        logger.exception("Fatal application error")
        QMessageBox.critical(None, config.window_name, str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())