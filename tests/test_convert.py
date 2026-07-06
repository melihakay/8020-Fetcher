"""Tests for convert.py — golden text for CCI1 (ROADMAP §0.5).

The expected text deviates from the ROADMAP's literal §0.5 snippet in one
respect: a blank line is emitted after the last step inside the 3x block.
This is required by intervals.icu to correctly terminate the repeat block —
without it, all subsequent steps are included inside the repeat.
(Verified against intervals.icu workout format documentation.)
"""

from eticu.convert import _format_distance_run, _format_distance_swim, _format_time, convert
from eticu.models import RepeatBlock, Step, Workout


def _cci1_workout() -> Workout:
    """Construct the CCI1 Ride workout from ROADMAP §0.5 raw data."""
    return Workout(
        name="CCI1",
        sport="Ride",
        pool_length_m=None,
        elements=[
            Step(kind="time", value=300.0, zone_8020="Zone 1", intensity="warmup"),
            Step(kind="time", value=1200.0, zone_8020="Zone 2", intensity="active"),
            RepeatBlock(
                count=3,
                children=[
                    Step(kind="time", value=300.0, zone_8020="Zone 3", intensity="active"),
                    Step(kind="time", value=180.0, zone_8020="Zone 1", intensity="recovery"),
                ],
            ),
            Step(kind="time", value=300.0, zone_8020="Zone 2", intensity="active"),
            Step(kind="time", value=360.0, zone_8020="Zone 1", intensity="cooldown"),
        ],
    )


# ---------------------------------------------------------------------------
# Golden text: HR mode (default)
# ---------------------------------------------------------------------------

_CCI1_HR_TEXT = """\
- Warmup 8020/Z1 5m Z1 HR
- 8020/Z2 20m Z2 HR

3x
- 8020/Z3 5m Z4 HR
- Recovery 8020/Z1 3m Z1 HR

- 8020/Z2 5m Z2 HR
- Cooldown 8020/Z1 6m Z1 HR"""


def test_cci1_hr_default() -> None:
    assert convert(_cci1_workout()) == _CCI1_HR_TEXT


def test_cci1_hr_explicit_flag() -> None:
    assert convert(_cci1_workout(), cycling_power=False) == _CCI1_HR_TEXT


# ---------------------------------------------------------------------------
# Golden text: Power mode (--cycling-power)
# ---------------------------------------------------------------------------

_CCI1_POWER_TEXT = """\
- Warmup 8020/Z1 5m Z1
- 8020/Z2 20m Z2

3x
- 8020/Z3 5m Z4
- Recovery 8020/Z1 3m Z1

- 8020/Z2 5m Z2
- Cooldown 8020/Z1 6m Z1"""


def test_cci1_power_mode() -> None:
    assert convert(_cci1_workout(), cycling_power=True) == _CCI1_POWER_TEXT


def test_cci1_power_zone3_maps_to_z4() -> None:
    """80/20 Zone 3 must produce Z4 target even in power mode."""
    text = convert(_cci1_workout(), cycling_power=True)
    assert "8020/Z3" in text
    # The target for that step must be Z4 (not Z3 HR and not Z3)
    lines = text.splitlines()
    z3_line = next(ln for ln in lines if "8020/Z3" in ln)
    assert z3_line == "- 8020/Z3 5m Z4"


# ---------------------------------------------------------------------------
# Run workouts always use HR regardless of --cycling-power
# ---------------------------------------------------------------------------


def test_run_always_hr() -> None:
    run_workout = Workout(
        name="RunTest",
        sport="Run",
        pool_length_m=None,
        elements=[
            Step(kind="time", value=600.0, zone_8020="Zone 2", intensity="active"),
        ],
    )
    text = convert(run_workout, cycling_power=True)
    assert "Z2 HR" in text
    assert text == "- 8020/Z2 10m Z2 HR"


def test_swim_always_hr() -> None:
    swim_workout = Workout(
        name="SwimTest",
        sport="Swim",
        pool_length_m=25,
        elements=[
            Step(kind="distance", value=400.0, zone_8020="Zone 2", intensity="active"),
        ],
    )
    text = convert(swim_workout, cycling_power=True)
    assert "Z2 HR" in text


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------


def test_time_minutes_only() -> None:
    assert _format_time(300.0) == "5m"
    assert _format_time(1200.0) == "20m"
    assert _format_time(180.0) == "3m"
    assert _format_time(360.0) == "6m"


def test_time_hours_and_minutes() -> None:
    assert _format_time(3661.0) == "1h1m1s"
    assert _format_time(3600.0) == "1h"
    assert _format_time(90.0) == "1m30s"


def test_distance_run_km() -> None:
    assert _format_distance_run(1000.0) == "1.0km"
    assert _format_distance_run(1600.0) == "1.6km"
    assert _format_distance_run(5000.0) == "5.0km"


def test_distance_swim_mtr() -> None:
    # 'mtr' suffix (not 'm') to avoid confusion with minutes.
    assert _format_distance_swim(400.0) == "400mtr"
    assert _format_distance_swim(1000.0) == "1000mtr"
    assert _format_distance_swim(410.0) == "400mtr"  # rounded to nearest 25


# ---------------------------------------------------------------------------
# Repeat block blank-line terminator
# ---------------------------------------------------------------------------


def test_repeat_blank_line_terminator() -> None:
    """Blank line must follow last step in repeat when more steps come after."""
    text = convert(_cci1_workout())
    lines = text.splitlines()
    # Find the blank line index
    blank_indices = [i for i, ln in enumerate(lines) if ln == ""]
    assert len(blank_indices) == 2, f"Expected exactly 2 blank lines, got: {blank_indices}"
    blank_idx = blank_indices[1]
    # The line before blank should be the last step inside 3x (Zone 1 3m)
    assert "8020/Z1" in lines[blank_idx - 1]
    assert "3m" in lines[blank_idx - 1]
    # The line after blank should be the post-repeat Zone 2 step
    assert "8020/Z2" in lines[blank_idx + 1]


def test_no_trailing_blank_line() -> None:
    """Workout ending with a repeat block should NOT have a trailing blank line."""
    workout = Workout(
        name="EndsWithRepeat",
        sport="Ride",
        pool_length_m=None,
        elements=[
            RepeatBlock(
                count=4,
                children=[
                    Step(kind="time", value=300.0, zone_8020="Zone 4", intensity="interval"),
                    Step(kind="time", value=180.0, zone_8020="Zone 1", intensity="recovery"),
                ],
            ),
        ],
    )
    text = convert(workout)
    assert not text.endswith("\n"), "Should not have trailing newline"
    assert not text.endswith("\n\n"), "Should not have trailing blank line"
