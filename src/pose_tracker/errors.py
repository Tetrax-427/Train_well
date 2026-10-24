class PoseTrackerError(Exception):
    """Base class for all application errors."""


class CameraError(PoseTrackerError):
    """Camera could not be opened or read."""


class ModelLoadError(PoseTrackerError):
    """Pose model file is missing or invalid."""

class PersistenceError(PoseTrackerError):
    """History database or snapshot storage failed."""


class SessionStateError(PoseTrackerError):
    """Operation not allowed in the current session phase."""

class CalibrationError(PoseTrackerError):
    """calibration.toml could not be read or holds invalid settings."""

class LlmError(PoseTrackerError):
    """The language-model server could not be reached or sent an unusable reply."""


class LlmConfigError(PoseTrackerError):
    """llm.toml could not be read or holds invalid settings."""


class ChatError(PoseTrackerError):
    """The assistant could not finish answering."""