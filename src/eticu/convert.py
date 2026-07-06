"""Convert a Workout model to intervals.icu workout description text.

Format notes (validated against intervals.icu documentation):
- Steps: "- [name] [duration] [target]"
- Time:  "5m", "30s", "1h", "5m30s"  ('m' = minutes)
- Distance run/ride: "2.0km"  (km, rounded to 0.1 km)
- Distance swim: "400mtr"  ('mtr' suffix for metres — 'mtr' ≠ 'm' which means minutes)
- HR target:    "Z1 HR"  (zone number + "HR" suffix)
- Power target: "Z1"     (bare zone, power is the default target type)
- Repeat:       "3x" on its own line; terminated by a BLANK LINE after the
                last step in the block — without the blank line, subsequent
                steps are interpreted as still inside the repeat.

NOTE: The ROADMAP §0.5 golden text omits the blank-line terminator.  That
omission is corrected here based on verified intervals.icu format rules.
"""

from __future__ import annotations

import logging

from eticu.models import Element, RepeatBlock, Step, Workout
from eticu.zones import icu_zone_label, step_label

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------


def _format_time(seconds: float) -> str:
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return "".join(parts) if parts else "0s"


def _format_distance_run(metres: float) -> str:
    """Round to nearest 0.1 km, emit as '2.0km'."""
    km = round(metres / 1000, 1)
    return f"{km:.1f}km"


def _format_distance_swim(metres: float) -> str:
    """Round to nearest 25 m, emit as '400mtr' ('mtr' ≠ 'm' = minutes)."""
    rounded = round(metres / 25) * 25
    return f"{int(rounded)}mtr"


def _format_duration(step: Step, sport: str) -> str:
    if step.kind == "time" and step.value > 0:
        return _format_time(step.value)
    if step.kind == "distance" and step.value > 0:
        if sport == "Swim":
            return _format_distance_swim(step.value)
        return _format_distance_run(step.value)
    return "lap"


# ---------------------------------------------------------------------------
# Target formatting
# ---------------------------------------------------------------------------


def _format_target(zone_8020: str | None, sport: str, cycling_power: bool) -> str:
    icu_zone = icu_zone_label(zone_8020)
    if sport == "Ride" and cycling_power:
        return icu_zone  # Power target: bare zone
    return f"{icu_zone} HR"  # HR target


# ---------------------------------------------------------------------------
# Step / block rendering
# ---------------------------------------------------------------------------


def _render_step(step: Step, sport: str, cycling_power: bool) -> str:
    if step.zone_8020 is None and step.intensity not in ("rest", "recovery", "warmup", "cooldown"):
        logger.warning("Step has no zone; defaulting to 8020/Z1 (Z1)")
    label = step_label(step.zone_8020)
    duration = _format_duration(step, sport)
    target = _format_target(step.zone_8020, sport, cycling_power)

    prefix = ""
    if step.intensity and step.intensity not in ("active", "interval", "other"):
        prefix = f"{step.intensity.capitalize()} "

    return f"- {prefix}{label} {duration} {target}"


def _render_elements(
    elements: list[Element],
    sport: str,
    cycling_power: bool,
) -> list[str]:
    lines: list[str] = []
    for i, elem in enumerate(elements):
        if isinstance(elem, Step):
            lines.append(_render_step(elem, sport, cycling_power))
        elif isinstance(elem, RepeatBlock):
            if i > 0 and (not lines or lines[-1] != ""):
                lines.append("")
            lines.append(f"{elem.count}x")
            lines.extend(_render_elements(elem.children, sport, cycling_power))
            # Blank line terminates the repeat block in intervals.icu format.
            # Without it, subsequent steps are treated as inside the block.
            if i < len(elements) - 1:
                lines.append("")
    return lines


def convert(workout: Workout, cycling_power: bool = False) -> str:
    """Render a Workout as intervals.icu workout description text.

    Args:
        workout: The parsed workout.
        cycling_power: If True and sport is Ride, emit Power zone targets
                       instead of HR.  Run/Swim always use HR regardless.
    """
    lines = _render_elements(workout.elements, workout.sport, cycling_power)
    return "\n".join(lines)
