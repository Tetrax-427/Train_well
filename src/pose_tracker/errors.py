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