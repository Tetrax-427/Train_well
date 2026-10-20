# Pose Tracker (Train_well)

A desktop gym-form tracker. It watches you through a webcam, draws a skeleton on you, counts
reps, checks your form against configurable rules, and after each set shows what went wrong
using **your own photo** with a corrected "ghost" pose drawn on it. Sets can be saved with a
weight to track progress over time.

Everything runs locally. Nothing leaves your machine.

## What it does

- **Live tracking:** MediaPipe pose estimation with temporal smoothing, one person, plus
  derived neck and mouth-centre points.
- **15 exercises:** squat, deadlift, hip thrust, calf raise, bench press, incline press,
  decline press, shoulder press, lateral raise, push-up, lat pulldown (wide and close grip),
  bent-over row, bicep curl, plank.
- **Form checks:** each exercise has rules (depth, lockout, lean, sway, path, wobble, tempo,
  and so on) with written explanations of why each matters.
- **View gating:** exercises declare side or front view. The app detects your view and tells
  you to turn.
- **Session summary** after Stop, with mistakes grouped, explained and counted.
- **History tab:** every session saved, with snapshot cards: your photo, your skeleton (red on
  the joints at fault), the purple corrected pose, measured vs needed values and the
  explanation.
- **Progress tab:** save a set with weight and reps, then see reps and weight per set per day
  and a training-volume line over 2, 7, 30, 90 days or all time.
- **Calibration file:** every limit adjustable in one `calibration.toml`. See `CALIBRATION.md`.

## Quick start

Requires Python 3.11, a webcam, and macOS (developed on Apple silicon).

```bash
cd ~/dev/Train_well
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install mediapipe PySide6 numpy pytest
pip uninstall -y opencv-contrib-python opencv-python opencv-python-headless opencv-contrib-python-headless
pip install opencv-python-headless
mkdir -p models && curl -L -o models/pose_landmarker_full.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
```

Why the OpenCV swap: `mediapipe` pulls in a build of OpenCV that bundles its own Qt, which
breaks PySide6 ("Could not find the Qt platform plugin cocoa"). The headless build has no
Qt. Repeat the swap whenever you recreate the venv.

Run the app and the tests (from the project root):

```bash
PYTHONPATH=src python -m pose_tracker.ui          # the app
PYTHONPATH=src pytest -v                           # tests
PYTHONPATH=src python -m pose_tracker.calibrate init   # create calibration.toml
```

> **Keep the project out of iCloud-synced folders** (Desktop, Documents). Syncing duplicates
> and corrupts files inside `.venv`. This project lives in `~/dev`.

Camera: place it at about hip height, 2 to 3 m away, with your whole body in frame. Side-view
exercises need you exactly side-on. Front-view ones (lateral raise, pulldowns) need you
facing the camera.

## How it works

```
camera ─► pose estimation ─► smoothing ─► derived points ─► session controller
                                                                  │
            ┌───────────────────── per frame, while a session is active ┘
            ▼
  view check ─► choose visible side ─► features (angles, offsets)
            ─► rep detector ─► per-rep rules ─► rep result
            ─► recorders (SQLite history + snapshots, text log)
```

1. **Capture thread:** reads the camera and runs the pose model off the UI thread. If the UI
   is busy it drops frames but still estimates every frame, so tracking stays continuous.
2. **Pose pipeline:** the raw 33 MediaPipe landmarks are smoothed with a One Euro filter,
   then neck and mouth-centre are derived.
3. **Analyzer** (once per frame): classifies the camera view, picks the better-visible side,
   computes features, and feeds the exercise's driving angle into the rep detector.
4. **Rep detector:** a state machine with hysteresis. It must see the resting position
   before arming, so jitter cannot create phantom reps.
5. **Rules:** when a rep completes, each rule inspects the rep's samples and may return a
   violation (measured value, limit, the moment it happened, a snapshot of the pose).
6. **Recorders:** the finished rep is stored with the nearest buffered camera frame as the
   snapshot of each mistake.

## Architecture

Layers with a strict dependency rule: **inner layers never import outer ones.**

```
domain  ◄──  application  ◄──  infrastructure / ui
(pure logic)  (use cases)       (OpenCV, MediaPipe, SQLite, Qt)
```

- **`domain`**: pure Python. No OpenCV, Qt or database. Easy to unit test and portable.
- **`application`**: orchestrates domain objects. Depends on `domain` and on the Protocol
  interfaces in `interfaces.py`, never on concrete libraries.
- **`infrastructure`**: concrete implementations of those interfaces (camera, MediaPipe,
  SQLite, JPEG encoding, file stores).
- **`ui`**: PySide6 views. Thin: presenters in `application` hold the logic and hand the
  widgets plain data.

SOLID in practice: exercises are data (Open/Closed), pose engines are swappable behind
`PoseEstimator` (Liskov), small focused interfaces (Interface Segregation), and the only place
concrete classes are wired together is `ui/__main__.py`, the composition root (Dependency
Inversion).

## Folder guide

```
Train_well/
├── calibration.toml          your limits (created by "calibrate init")
├── models/                   pose_landmarker_full.task (downloaded)
├── history/                  history.db and snapshots/<session_id>/*.jpg
├── sessions/                 one text log per session
├── tests/                    pytest suite; pose_factory.py builds synthetic poses
└── src/pose_tracker/
    ├── config.py             AppConfig: every default setting
    ├── errors.py             exception types
    ├── interfaces.py         Protocols: FrameSource, PoseEstimator, SessionWriter, ...
    ├── calibrate.py          command-line tool: init / check / show
    ├── __main__.py           legacy OpenCV-window entry point (needs non-headless OpenCV)
    ├── domain/
    │   ├── frame.py, pose.py            Frame, Landmark, Pose, LandmarkId, SKELETON
    │   ├── geometry.py                  Point2D, angle_at, distance, midpoint
    │   ├── filters.py, pose_smoother.py One Euro smoothing
    │   ├── derived.py                   neck and mouth-centre landmarks
    │   ├── view.py, body_side.py        view detection, left/right side choice
    │   ├── features.py                  BodyFeatures: all measurements
    │   ├── rep.py                       Rep, RepThresholds, RepDetector
    │   ├── form.py, motion_rules.py     rule classes
    │   ├── exercise.py                  Exercise definition
    │   ├── exercises/                   one file per exercise + catalog.py
    │   ├── rep_stats.py                 per-rep min/max of features
    │   ├── pose_correction.py           corrected ("ghost") poses per rule
    │   ├── rule_joints.py               which joints each rule is about
    │   ├── history.py, progress.py      stored-session and progress models
    ├── application/
    │   ├── pipeline.py, fps.py          legacy blocking pipeline
    │   ├── smoothed_estimator.py        decorators around a PoseEstimator
    │   ├── derived_landmarks_estimator.py
    │   ├── exercise_analyzer.py         view gating, features, reps, rules
    │   ├── session_controller.py        SELECT -> READY -> ACTIVE -> SUMMARY
    │   ├── training_presenter.py        live-screen data for the UI
    │   ├── session_summary.py           end-of-session report data
    │   ├── history_presenter.py         History tab data
    │   ├── progress_presenter.py        saving sets, chart queries
    │   ├── progress_layout.py           chart bar/slot geometry
    │   ├── frame_buffer.py              rolling JPEG buffer for snapshots
    │   ├── history_recorder.py, composite_recorder.py
    │   ├── geometric_reference.py       reference-pose provider
    │   ├── position_hint.py, exercise_hud.py
    │   ├── catalog_factory.py           builds exercises; section -> exercise key map
    │   └── calibration.py               applies and validates calibration data
    ├── infrastructure/
    │   ├── opencv_camera.py, opencv_display.py, opencv_renderer.py
    │   ├── mediapipe_estimator.py       MediaPipe PoseLandmarker (VIDEO mode)
    │   ├── opencv_frame_encoder.py      downscale + JPEG
    │   ├── filesystem_snapshot_store.py
    │   ├── sqlite_session_repository.py history + progress storage
    │   ├── opencv_snapshot_painter.py   draws skeleton and ghost on a snapshot
    │   ├── text_rep_recorder.py         per-session text log
    │   └── calibration_file.py          reads calibration.toml
    └── ui/
        ├── __main__.py                  Qt composition root (the app)
        ├── capture_thread.py            camera + estimation off the UI thread
        ├── main_window.py               Train / History / Progress tabs
        ├── train_view.py, live_panel.py, video_widget.py, summary_view.py
        ├── history_view.py, session_detail_view.py, mistake_card.py
        ├── progress_view.py, progress_charts.py, progress_save_box.py
        ├── qt_helpers.py, theme.py
```

## Core concepts

**Pose and landmarks.** MediaPipe returns 33 points (nose, shoulders, elbows, wrists, hips,
knees, ankles, heels, toes and more) with x/y as fractions of the frame, plus a visibility
score. Two derived points are added: `NECK` and `MOUTH_CENTER`.

**Features** (`domain/features.py`). Measurements computed per frame for one side of the body
(knee angle, elbow angle, torso lean, hip sag, hand offset, and so on) and some for both sides
(lateral raise, pulldown). A feature is `None` when a needed landmark is not visible. All
angles are computed in image proportions (x scaled by width/height) so they are not skewed
by a 16:9 frame.

**View and side.** `ViewDetector` compares shoulder width to torso length to decide
FRONT / SIDE / ANGLED, with a stabiliser so the label does not flicker. For side-view
exercises the better-visible limb side is chosen and locked for the duration of a rep.

**Exercise** (`domain/exercise.py`). A declarative definition: key and name, required view,
the **driver** (the angle whose movement defines a rep), rep thresholds, a tuple of rules,
`lead_in_ms` (resting history kept with each rep), logged features, a position hint and an
`explanations` dict (rule id to a "why it matters" text). Hold exercises (plank) set
`timed=True`.

**Rep detection.** `RepThresholds(rest, leave)` define a band. A rep starts when the driver
leaves rest past the `leave` value and ends on returning to rest. Direction is inferred
from the values (dip or rise). Reps shorter than `min_rep_ms` are discarded.

**Rules.** Each rule evaluates a finished rep and returns a `FormViolation` or nothing.

| Rule | Meaning |
|---|---|
| ReachBelow / ReachAbove | must get down to / up to a target |
| StayBelow / StayAbove | must never exceed / drop below a limit |
| StayStill | spread of a feature must stay small |
| BandAtRest / BandAtPeak / MedianBand | typical or setup value must sit in a range |
| DriftFromRest | change from the setup baseline (absolute or relative) |
| PathDeviation | hand strays from a straight line (path) |
| Steadiness | hand shake around its moving average (wobble) |
| TempoRule | rep faster than a minimum duration |

**Ghost pose.** For rules with a computable target, `domain/pose_correction.py` rebuilds your
stored pose with limb lengths kept and only the faulty segment moved so the measurement
reaches the rule's limit. The painter draws it in purple under your skeleton on the snapshot.
Rules about movement over time (wobble, path, tempo) have no ghost.

## Session lifecycle

`SessionController` is a small state machine:

```
SELECT ─select─► READY ─start─► ACTIVE ─stop─► SUMMARY ─back─► SELECT
```

- Exercises can be switched in SELECT, READY and SUMMARY, never while ACTIVE.
- **One Start to Stop is one set.** Each Start builds a fresh analyzer and recorder, so a
  stored session is always one exercise.
- READY shows the live view check without counting anything.
- Closing the window mid-session asks for confirmation, finalizes the session and saves reps.

## Data and storage

- **`history/history.db`** (SQLite, schema version 2): `sessions` (exercise, start/end times,
  progress flag, reps, weight), `reps` (timing, per-rep feature ranges) and `violations`
  (rule, message, explanation, measured vs limit, landmarks, snapshot key).
- **`history/snapshots/<session_id>/rep<N>_<rule>.jpg`**: clean snapshot JPEGs (no skeleton).
  The skeleton and ghost are drawn when you view a card, so they can be toggled.
- **`sessions/*.txt`**: a text log per session: each rep's feature min/max and any violations.
- **Progress:** saving a set marks the session with its reps and weight (empty weight means
  bodyweight). Volume is the sum of weight × reps, or total reps when no weight exists.
- A v1 database upgrades itself to v2 when opened.

Snapshots are photos of you stored locally. Deleting a session in History removes its rows
and its snapshot folder. Add `history/`, `sessions/`, `.venv/` to `.gitignore`.

## Configuration

Defaults live in `AppConfig` (`config.py`). To change limits, use `calibration.toml` and the
calibrate tool. See `CALIBRATION.md`. The file is read at startup. A missing file means
defaults, and an invalid file stops the app with a list of every problem.

## Adding a new exercise

1. **Features:** if you need a new measurement, add a field to `BodyFeatures` and compute it in
   `compute_features` (`domain/features.py`).
2. **Exercise file:** create `domain/exercises/<name>.py` with a frozen `<Name>Settings`
   dataclass (all thresholds as fields with defaults) and a `build_<name>()` returning an
   `Exercise` with rules, explanations, `logged_features` and a `position_hint`. Reuse
   existing rule classes where possible.
3. **Register it:**
   - `domain/exercises/catalog.py`: add the settings parameter and the builder to the tuple
     (order is the order shown in the app).
   - `config.py`: add the settings field to `AppConfig`.
   - `application/catalog_factory.py`: pass the setting in `catalog_for` and add the
     section-to-key entry in `SECTION_EXERCISES`. This is what makes it calibratable.
4. **History display:** add each rule to `_ROLES` in `domain/rule_joints.py` (which joints to
   mark red). For front-view rules, also add to `_BILATERAL`.
5. **Ghost pose:** add a corrector to `_CORRECTORS` in `domain/pose_correction.py`, or list
   the rule in `NO_GHOST` in `tests/test_pose_correction.py`.
6. **Tests:** add a synthetic pose factory to `tests/pose_factory.py` and a
   `tests/test_<name>.py` that runs a clean rep and one case per rule. Existing guard tests
   will fail if you skip any of: an explanation for every rule, a joint mapping for every
   rule, a ghost decision for every rule, and a calibration section for every exercise.

## Testing

```bash
PYTHONPATH=src pytest -v
```

Domain logic is tested with synthetic poses (`tests/pose_factory.py`) that let a test set an
exact knee angle, hip sag and so on, so no camera is needed. Infrastructure tests use temporary
directories and in-memory fakes. Qt widgets themselves are not unit tested. Their logic lives
in presenters, which are.

If a test sets a value exactly on a rep threshold, floating-point rounding can push it to the
wrong side. Keep synthetic values clearly inside or outside the bands.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Could not find the Qt platform plugin "cocoa"` | Use `opencv-python-headless` (see Quick start). If it persists, make sure the project is not in an iCloud-synced folder and recreate the venv. |
| `Model file not found` | Download `models/pose_landmarker_full.task` (Quick start). |
| Camera permission error on macOS | Allow your terminal under System Settings, Privacy & Security, Camera, then restart it. |
| No reps counted | Check the banner: view (turn sideways / face the camera) and full body in frame. Then see `CALIBRATION.md`. |
| `calibration.toml` ignored | You ran the app from a different folder, or did not restart. |
| MediaPipe prints `inference_feedback_manager` warnings | Harmless. |

## Known limitations

- 2D measurements from one camera, only trustworthy when you are really side-on (or facing
  the camera for front-view exercises).
- MediaPipe has no spine landmarks. Back rounding and arching are estimates.
- Heel, toe and wrist landmarks are noisy. Expect to calibrate calf raise, hip thrust and
  anything wobble-based.
- One person is tracked. Lat pulldown is front view only, so leaning back too far cannot be
  seen.
- All limits are starting guesses until you calibrate them.
- This is a form aid, not medical or coaching advice.

_______________________________________________________________________________________________________
### To run all TESTS:
- PYTHONPATH=src pytest -v

### To run the UI:
- PYTHONPATH=src python -m pose_tracker.ui