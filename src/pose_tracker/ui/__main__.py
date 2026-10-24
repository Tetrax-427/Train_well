from __future__ import annotations

import logging
import sys
from contextlib import ExitStack, closing
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox

from pose_tracker.application.calibration import calibrate, summarize
from pose_tracker.application.composite_recorder import SessionRepRecorder
from pose_tracker.application.derived_landmarks_estimator import DerivedLandmarksEstimator
from pose_tracker.application.frame_buffer import FrameBuffer
from pose_tracker.application.geometric_reference import GeometricReferenceProvider
from pose_tracker.application.history_presenter import HistoryPresenter
from pose_tracker.application.history_recorder import HistoryRepRecorder
from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.application.routine_presenter import RoutinePresenter
from pose_tracker.application.session_controller import SessionController
from pose_tracker.application.smoothed_estimator import SmoothedPoseEstimator
from pose_tracker.application.training_presenter import TrainingPresenter
from pose_tracker.config import AppConfig
from pose_tracker.errors import CalibrationError, LlmConfigError, PoseTrackerError
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
from pose_tracker.infrastructure.sqlite_routine_repository import SqliteRoutineRepository
from pose_tracker.infrastructure.sqlite_session_repository import SqliteSessionRepository
from pose_tracker.infrastructure.text_rep_recorder import TextFileRepRecorder
from pose_tracker.ui.capture_thread import CaptureThread
from pose_tracker.ui.history_view import HistoryView
from pose_tracker.ui.main_window import MainWindow
from pose_tracker.ui.progress_view import ProgressView
from pose_tracker.ui.routines_view import RoutinesView
from pose_tracker.ui.theme import STYLE_SHEET
from pose_tracker.ui.train_view import TrainView
from pose_tracker.application.chat.digest import TrainingDigest
from pose_tracker.application.chat.budget import estimate_tokens, plan_budget, tools_tokens
from pose_tracker.application.chat.agent import ChatAgent
from pose_tracker.application.chat.llm_settings import parse_llm_settings
from pose_tracker.application.chat.system_prompt import build_system_prompt
from pose_tracker.application.chat.tool_registry import ToolRegistry
from pose_tracker.application.chat.tools import default_tools
from pose_tracker.application.chat.unavailable_llm import UnavailableLlmClient
from pose_tracker.infrastructure.llm_settings_file import read_llm_settings_file
from pose_tracker.infrastructure.openai_compatible_client import OpenAiCompatibleClient
from pose_tracker.interfaces import LlmClient
from pose_tracker.ui.chat_view import ChatView

logger = logging.getLogger(__name__)


def _llm_client(config: AppConfig) -> tuple[LlmClient, LlmSettings]:
    """The chat backend. A broken llm.toml disables only the Chat tab, not the app."""
    try:
        settings = parse_llm_settings(read_llm_settings_file(config.llm_file), config.llm_file)
    except LlmConfigError as exc:
        logger.error("%s", exc)
        return UnavailableLlmClient(str(exc)), LlmSettings()
    return OpenAiCompatibleClient(settings), settings

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
            routine_repository = stack.enter_context(closing(
                SqliteRoutineRepository(config.history_dir / "routines.db")
            ))

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
            routines = RoutinePresenter(routine_repository, names)
            llm, llm_settings = _llm_client(base)
            today = datetime.now().date()
            all_tools = ToolRegistry(default_tools(
                catalog, repository, repository, routine_repository, datetime.now
            ))
            budget = plan_budget(
                llm_settings.context_tokens,
                llm_settings.max_tokens,
                base_prompt_tokens=estimate_tokens(build_system_prompt(today, names)),
                tool_tokens=tools_tokens(all_tools.specs),
            )
            logger.info("Chat budget: %s", budget)
            digest = TrainingDigest(
                names, repository, repository, routine_repository, datetime.now
            )
            agent = ChatAgent(
                llm,
                all_tools if budget.tools_enabled else ToolRegistry([]),
                system_prompt=lambda: build_system_prompt(
                    datetime.now().date(), names, digest.text(budget.digest_chars),
                    tools=budget.tools_enabled,
                ),
                max_tool_steps=llm_settings.max_tool_steps,
                max_tool_chars=budget.tool_result_chars,
                max_history_turns=llm_settings.max_history_turns,
                context_tokens=budget.context_tokens,
                reply_tokens=budget.reply_tokens,
            )
            chat_view = ChatView(agent, f"{llm_settings.model} · {llm_settings.base_url}")
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
                TrainView(presenter, CaptureThread(camera, estimator), progress, routines),
                RoutinesView(routines),
                history_view,
                ProgressView(progress),
                chat_view,
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