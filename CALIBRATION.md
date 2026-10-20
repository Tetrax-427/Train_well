# Calibration guide

Every form check in the app (squat depth, elbow lockout, hip sag, and so on) compares a
measurement from the camera with a **limit**. The default limits are starting guesses. Your
camera angle, height, lighting and body proportions all shift the numbers, so the defaults
will sometimes flag good reps or miss bad ones.

Calibration means adjusting those limits to fit you. Everything is done in one file,
`calibration.toml`. You never edit code.

## 1. Before you start

- The app runs: `PYTHONPATH=src python -m pose_tracker.ui`
- You are in the project folder (the one containing `src/`), with the virtual environment active.
- Create the calibration file once:

```bash
PYTHONPATH=src python -m pose_tracker.calibrate init
```

This writes `calibration.toml` with every setting listed and **commented out**. Nothing changes
until you uncomment a line. `init` refuses to overwrite an existing file unless you add
`--force` (which discards your calibration).

Without a `calibration.toml`, the app uses the built-in defaults. The file only holds the
values you change. Anything missing keeps its default.

> The app looks for `calibration.toml` relative to the folder you run it from. Always run
> from the project root.

## 2. The file in two minutes

```toml
[curl]
max_unsteadiness = 0.04          # slow reps were flagged as jerky
top_elbow_angle = 60.0

[squat]
disabled_rules = ["torso_lean"]  # stop checking forward lean for now
```

- **`[section]`** is one exercise (or `[view_thresholds]` / `[smoothing]`). Names are in the
  reference tables below.
- **`setting = value`** changes one limit. Lines starting with `#` are comments.
- **`disabled_rules = [...]`** switches checks off for that exercise. Reps are still counted.
- Whole-number settings (`lead_in_ms`, `min_hold_ms`, `pose_grace_ms`) need integers (`2000`).
  Other numbers can be written as `55` or `55.0`. Booleans are lowercase `true` / `false`.
- Each `[section]` may appear only once.
- **Restart the app** after editing. The file is read at startup.

## 3. Commands

```bash
PYTHONPATH=src python -m pose_tracker.calibrate check        # validate, list what changes
PYTHONPATH=src python -m pose_tracker.calibrate show curl    # settings the app will use
PYTHONPATH=src python -m pose_tracker.calibrate show        # everything
PYTHONPATH=src python -m pose_tracker.calibrate init        # create the file (never overwrites)
```

- `check` exits with an error message for typos, wrong types or impossible values. It lists
  **every** problem at once and suggests the name you probably meant.
- `show` marks values that differ from the defaults with `<- calibrated`.
- A different file: `python -m pose_tracker.calibrate --file other.toml check`.
- If the file is invalid when you start the app, the app shows the problem list and exits.
  It never trains on settings you did not intend.

## 4. Step-by-step calibration

Calibrate **one exercise, one rule at a time**. The routine is the same for every rule.

### Step 1: Pick an exercise and set up the camera

Use the setup the app's banner describes (side-on or facing the camera, whole body in frame).
**Keep the camera in the same position for the whole calibration**, because moving it changes
every number.

### Step 2: Record a clean set and a sloppy set

For the exercise you picked:

1. Start a session, do **5 reps with good form**, stop.
2. Start another, do **5 reps with the mistake you want to catch** (shallow depth, swinging,
   sagging hips, and so on), stop.
3. Do not save them to Progress. They are test data.

Each Start to Stop session makes one history session and one text log.

### Step 3: Read the numbers

There are three places, from easiest to most detailed.

**a) The text log**: the newest file in `sessions/`.

```
Rep 2 | 15:30:25 | 2.1s | 2 issue(s)
  knee_angle: min 118.4, max 174.0
  torso_lean_deg: min 12.5, max 58.9
  ! squat_depth: Go deeper... (measured 118.4, limit 100.0, at 12.3s into session)
```

- The `min` / `max` lines are written for **every** rep, whether or not a rule fired. They show
  your real range (for example, how deep you actually went).
- `! rule_id` lines appear only when a rule fired. They show the measured value and the limit.

**b) The History tab.** Each mistake card says "Measured 118.4, needed 100.0 or less". The
phrase **"or less" / "or more"** tells you which side of the limit is good.

**c) The database**, for comparing many reps:

```bash
sqlite3 history/history.db "SELECT s.id, r.rep_number, v.rule_id, v.measured, v.limit_value
FROM violations v JOIN reps r ON r.id = v.rep_id JOIN sessions s ON s.id = r.session_id
WHERE s.exercise_key = 'bicep_curl' ORDER BY s.id DESC, r.rep_number;"
```
(Use the exercise key from the reference tables.)

### Step 4: Some rules only report when they fire. Force them

Wobble and path rules (`control`, `bar_path`) are not in the min / max lines. To read their
values, **temporarily make the rule always fire**, so every rep reports its measured value:

| Rule type (see "Must be" in the tables) | Set the limit to | The logged value is |
|---|---|---|
| `max` (must never exceed) | `0.0` | your highest value |
| `reach ≥` (must get up to) | `180` | your highest value |
| `reach ≤` (must get down to) | `0.0` | your lowest value |
| `min` (must never go below) | `180` | your lowest value |
| `spread` (must not vary more) | `0.0` | your actual spread |
| `band` (inside a range) | read it from the log's min / max lines instead | |

Signed measurements (hip sag, back tilt, layback) can be negative. Forcing with `0.0` will not
fire when you stay on the negative side, so read those from the min / max lines.

Put the limit back to its real value afterwards.

### Step 5: Choose the limit

You now have two groups of numbers: **clean reps** and **sloppy reps**.

- **Set the limit between the two groups, nearer the clean side** (about one third of the
  way from the clean group). That keeps good reps from being flagged while still catching the
  mistake.
- **If the groups overlap**, the measurement cannot separate good form from bad on your
  setup. Do not loosen it until it never fires. Either disable that rule (section 6) or move
  the camera and repeat.
- **Check the direction.** Some names mislead: the shoulder press `bottom_elbow_angle` means
  "get down to this or lower", but the curl `bottom_elbow_angle` means "get up to this or
  higher". The tables below spell it out.
- **Change one rule at a time**, so you know what fixed what.

### Step 6: Edit, check, restart

1. Open `calibration.toml`, uncomment the setting and edit it.
2. Run `check`.
3. Restart the app.

### Step 7: Verify

Do a clean set and a sloppy set again. The clean one should come back clean. The sloppy one
should be flagged. Repeat steps 2 to 7 until you are happy. Then remove any temporary forcing.

### Worked example (illustrative numbers)

The curl wobble check flags slow reps as jerky.

1. In `calibration.toml`:
```toml
   [curl]
   max_unsteadiness = 0.0
```
2. Do 5 slow reps, then 5 fast bouncing reps. Read the `! control ... (measured X ...)` lines.
3. Suppose the slow reps read `0.012` to `0.020` and the fast ones `0.035` to `0.060`.
4. The groups do not overlap, so set the limit at roughly `0.028`:
```toml
   [curl]
   max_unsteadiness = 0.028
```
5. `check`, restart, repeat both sets, confirm.

## 5. Units

| Looks like | Unit |
|---|---|
| `*_angle`, `*_deg` | degrees |
| `max_path_deviation`, `max_unsteadiness`, `max_hand_drift`, offsets | torso lengths (your shoulder-to-hip distance) |
| `max_bar_tilt`, `*_grip_ratio` | shoulder widths |
| `max_shrug`, `max_chord_shrink` | fraction (`0.08` = 8%) |
| `*_ms` | milliseconds |
| `min_rep_seconds` | seconds |

## 6. Switching a check off

```toml
[squat]
disabled_rules = ["torso_lean"]
```

- Rule names are listed in each exercise's comment in `calibration.toml` and in the tables
  below.
- A wrong rule name is rejected with the list of valid names.
- Disabled checks are not evaluated, shown or saved, but reps are still counted.
- To turn it back on, remove the name from the list.

## 7. Settings that are not form checks

**Rep detection (`rest_*` and `leave_*`).** These decide when a rep starts and ends. The
`rest` value is where you are at rest, and the `leave` value is how far you must move away
before a rep counts. The gap between them (hysteresis) stops jitter from creating phantom
reps.

- **Keep `rest` and `leave` on the same sides of each other as the defaults.** For example,
  squat has `rest` 160 above `leave` 150. Swapping them would make rep counting run backwards,
  so `check` rejects it.
- Reps not counted? Make `leave` less demanding (closer to `rest`). Phantom reps from jitter?
  Widen the gap.

**`lead_in_ms`.** How much of the resting position before a rep is kept with it. Rules that
judge the start or top position (bar over mid-foot, hand placement, shrug baseline) use it.

**`[view_thresholds]`.** Decide when you count as side-on or facing the camera, from the ratio
of shoulder width to torso length.

| Setting | Default | Meaning |
|---|---|---|
| `side_max_ratio` | 0.30 | at or below this you are SIDE |
| `front_min_ratio` | 0.55 | at or above this you are FRONT |
| `min_visibility` | 0.5 | landmark confidence needed |

View flickers or says ANGLED while you are side-on: raise `side_max_ratio` (try 0.40).
`side_max_ratio` must stay below `front_min_ratio`.

**`[smoothing]`.** Controls how much the skeleton is smoothed. `min_cutoff` (default 1.0): lower
means steadier at rest. `beta` (10.0): higher means less lag during fast movement. If the
skeleton jitters when you stand still, lower `min_cutoff`. If it lags behind fast reps, raise
`beta`.

## 8. Reference: sections, rules and settings

**Must be** legend: `reach ≤` = must get down to this or lower, `reach ≥` = must get up to
this or higher, `max` = must never exceed, `min` = must never drop below, `spread` = must
not vary by more than this, `band` = typical value must sit inside the range.

This table shows defaults at the time of writing. `calibrate show <section>` always prints
the real current values.

### Squat: `[squat]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| squat_depth | target_knee_angle (100.0) | reach ≤ |
| torso_lean | max_torso_lean_deg (50.0) | max |

Rep: `rest_knee_angle` (160.0), `leave_knee_angle` (150.0).

### Shoulder press: `[shoulder_press]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| press_bottom | bottom_elbow_angle (100.0) | reach ≤ |
| press_lockout | lockout_elbow_angle (165.0) | reach ≥ |
| layback | max_layback_deg (15.0) | max |
| bar_path | max_path_deviation (0.15) | max |
| control | max_unsteadiness (0.015) | max |
| leg_drive | max_leg_movement_deg (20.0) | spread |

Rep: `rest_elbow_angle` (125.0), `leave_elbow_angle` (140.0), `lead_in_ms` (1500).

### Push-up: `[push_up]`, side view (key `push_up`)
| Rule | Setting (default) | Must be |
|---|---|---|
| pushup_depth | bottom_elbow_angle (95.0) | reach ≤ |
| pushup_lockout | lockout_elbow_angle (165.0) | reach ≥ |
| hip_sag | max_hip_sag_deg (12.0) | max |
| hip_pike | max_hip_pike_deg (12.0) | max (hips above the line) |
| knee_bend | min_knee_angle (160.0) | min |
| head_position | min_neck_angle (145.0) | min |
| hand_placement | max_hand_offset (0.3) | band ±value |

Rep: `rest_elbow_angle` (150.0), `leave_elbow_angle` (135.0). Plank gate:
`max_plank_incline_deg` (35.0).

### Deadlift: `[deadlift]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| start_back | max_start_torso_deg (70.0) | band 0..value, at setup |
| hips_shoot_up | max_torso_drift_deg (10.0) | max change |
| back_rounding | max_chord_shrink (0.08) | max drop |
| lockout_arch | max_layback_deg (5.0) | max |
| head_position | min_neck_angle (150.0) | min |
| hip_extension | lockout_hip_angle (170.0) | reach ≥ |
| knee_lockout | lockout_knee_angle (170.0) | reach ≥ |
| arms_straight | min_elbow_angle (160.0) | min |
| bar_start | max_bar_start_offset (0.15) | band ±value, at setup |
| bar_forward | max_bar_forward_drift (0.2) | max |
| start_knees | min_start_knee_angle (100.0) | band value..180, at setup |
| control | max_unsteadiness (0.015) | max |

Rep: `rest_hip_angle` (110.0), `leave_hip_angle` (125.0).

### Bicep curl: `[curl]`, side view (key `bicep_curl`)
| Rule | Setting (default) | Must be |
|---|---|---|
| curl_top | top_elbow_angle (55.0) | reach ≤ |
| curl_bottom | bottom_elbow_angle (160.0) | reach ≥ |
| elbow_drift | max_upper_arm_angle (30.0) | max |
| torso_swing | max_torso_swing_deg (10.0) | spread |
| control | max_unsteadiness (0.015) | max |

Rep: `rest_elbow_angle` (150.0), `leave_elbow_angle` (140.0).

### Bench press: `[bench_press]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| bench_depth | bottom_elbow_angle (95.0) | reach ≤ |
| bench_lockout | lockout_elbow_angle (165.0) | reach ≥ |
| hips_lifted | max_hip_lift_deg (12.0) | max |
| back_arch | max_arch_deg (12.0) | max (shoulders above hips) |
| bar_path | max_path_deviation (0.15) | max |
| bar_drift | max_hand_drift (0.30) | spread |
| control | max_unsteadiness (0.03) | max |
| head_position | min_neck_angle (145.0) | min |

Rep: `rest_elbow_angle` (155.0), `leave_elbow_angle` (140.0). Lying gate:
`max_lying_tilt_deg` (30.0).

### Incline press: `[incline_press]` and decline press: `[decline_press]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| bench_depth | bottom_elbow_angle (95.0) | reach ≤ |
| bench_lockout | lockout_elbow_angle (165.0) | reach ≥ |
| bench_angle | max_back_shift_deg (10.0) | spread |
| bar_path | max_path_deviation (0.15) | max |
| bar_drift | max_hand_drift (0.30) | spread |
| control | max_unsteadiness (0.03) | max |
| head_position | min_neck_angle (145.0) | min |

Bench-angle gate (reps only count inside it): `min_back_tilt_deg` / `max_back_tilt_deg`
(incline -65.0 / -15.0, decline 8.0 / 45.0). Rep: `rest_elbow_angle` (155.0),
`leave_elbow_angle` (140.0).

### Lateral raise: `[lateral_raise]`, front view
| Rule | Setting (default) | Must be |
|---|---|---|
| raise_height | min_raise_deg (80.0) | reach ≥ |
| raise_too_high | max_raise_deg (105.0) | max |
| arm_symmetry | max_arm_asymmetry_deg (15.0) | max |
| elbow_bend | min_arm_bend_deg (120.0) | min |
| shrugging | max_shrug (0.15) | max drop |
| body_sway | max_body_sway_deg (8.0) | spread |
| control | max_unsteadiness (0.03) | max |

Rep: `rest_raise_deg` (30.0), `leave_raise_deg` (45.0), `lead_in_ms` (1000).

### Plank: `[plank]`, side view (a hold counts as one rep)
| Rule | Setting (default) | Must be |
|---|---|---|
| hip_sag | max_hip_sag_deg (10.0) | max |
| hip_pike | max_hip_pike_deg (10.0) | max (hips above the line) |
| knee_bend | min_knee_angle (160.0) | min |
| head_position | min_neck_angle (145.0) | min |
| support_position | max_elbow_offset (0.3) | band ±value |
| hold_steady | max_hip_wobble_deg (8.0) | spread |

Hold: `min_hold_ms` (5000), `pose_grace_ms` (1500). Rep: `rest_incline_deg` (45.0),
`leave_incline_deg` (30.0).

### Lat pulldown: `[pulldown_wide]` and `[pulldown_close]`, front view
| Rule | Setting (default wide / close) | Must be |
|---|---|---|
| pulldown_depth | max_depth_elevation_deg (65.0 / 55.0) | reach ≤ |
| pulldown_stretch | min_stretch_deg (155.0) | reach ≥ |
| grip_width | min_grip_ratio (1.5 / 0.0), max_grip_ratio (3.0 / 1.1) | band |
| bar_level | max_bar_tilt (0.30) | max |
| control | max_unsteadiness (0.03) | max |

Rep: `rest_elevation_deg` (120.0), `leave_elevation_deg` (100.0).

### Hip thrust: `[hip_thrust]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| thrust_lockout | lockout_hip_angle (170.0) | reach ≥ |
| foot_placement | max_shin_angle_deg (20.0) | band 0..value, at the top |
| head_position | min_neck_angle (145.0) | min |
| thrust_tempo | min_rep_seconds (1.0) | rep not faster than this |

Rep: `rest_hip_angle` (135.0), `leave_hip_angle` (150.0). Lying gate: `max_gate_tilt_deg` (50.0).

### Bent-over row: `[bent_over_row]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| row_top | top_elbow_angle (105.0) | reach ≤ |
| row_stretch | bottom_elbow_angle (160.0) | reach ≥ |
| row_hinge | min_hinge_deg (30.0), max_hinge_deg (75.0) | band, at setup |
| torso_swing | max_torso_change_deg (15.0) | spread |
| back_rounding | max_chord_shrink (0.08) | max drop |
| bar_path | max_path_deviation (0.20) | max |
| control | max_unsteadiness (0.03) | max |
| head_position | min_neck_angle (140.0) | min |

Rep: `rest_elbow_angle` (150.0), `leave_elbow_angle` (135.0).

### Calf raise: `[calf_raise]`, side view
| Rule | Setting (default) | Must be |
|---|---|---|
| calf_height | min_raise_deg (18.0) | reach ≥ |
| knee_bend | min_knee_angle (165.0) | min |
| torso_swing | max_torso_change_deg (8.0) | spread |
| calf_tempo | min_rep_seconds (1.0) | rep not faster than this |

Rep: `rest_foot_angle` (8.0), `leave_foot_angle` (14.0). Heel and toe are noisy landmarks, so
calibrate `min_raise_deg` first.

## 9. Common problems

| Symptom | Likely cause and fix |
|---|---|
| Good reps flagged as jerky | `max_unsteadiness` too low for your camera noise. Calibrate it (worked example). |
| A rule never fires even on bad reps | Limit too loose. Compare clean vs sloppy numbers and tighten. |
| Clean and sloppy numbers overlap | The measurement cannot separate them on this setup. Move the camera, or disable the rule. |
| Rep count too low or too high | Adjust `rest_*` / `leave_*` (section 7). |
| Nothing counts, banner asks you to turn | View detection. Adjust `[view_thresholds]` or your position. |
| Skeleton jitters at rest / lags on fast reps | Adjust `[smoothing]`. |
| Back rounding flags constantly | It is an estimate from the shoulder-hip distance. Raise `max_chord_shrink` or disable it. |
| `check` says unknown setting | Typo. The message suggests the right name. |
| `check` says "cross over" | `rest_*` / `leave_*` swapped sides. Keep the default ordering. |
| Changes have no effect | You did not restart the app, or you ran it from a folder without the file. |

## 10. Good habits

- Keep the camera fixed during a calibration round.
- Calibrate with the weight you actually train with. Heavier weights change movement.
- Change one setting at a time and note the old value in a comment.
- Back up `calibration.toml` when you are happy with it.
- Mistake cards and logs reflect the limit that applied when the rep was recorded. Changing a
  limit later does not rewrite old sessions.

## 11. What calibration cannot fix

Measurements come from a single camera and are 2D, so they are only trustworthy when you are
truly side-on (or facing the camera for front-view exercises). MediaPipe has no spine points,
so back rounding and arching are estimates, not spine measurements. Heel, toe and wrist
landmarks are the noisiest. If a check keeps misfiring after calibration, disable it rather than
loosening it until it means nothing.