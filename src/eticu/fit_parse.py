"""Parse a .FIT workout file into the Workout model.

Key domain facts (full detail in ROADMAP §0):
- 80/20 uses target_type=open (2) — zone lives in the step's notes string.
- Repeat step: duration_type=6, duration_value=loop-back step index,
  target_value=repeat count.
- _build_tree() absorbs repeated steps back to the loop-back index,
  handling nested repeats correctly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitdecode  # type: ignore[import-untyped]

from eticu.models import Element, RepeatBlock, Step, Workout

logger = logging.getLogger(__name__)

# FIT SDK enum values for workout_step fields (Profile 21.x).
# duration_type
_DT_TIME = 0
_DT_DISTANCE = 1
_DT_OPEN = 5
_DT_REPEAT = 6  # repeat_until_steps_cmplt

# String aliases fitdecode may return for enum fields
_DURATION_TYPE_STR: dict[str, int] = {
    "time": _DT_TIME,
    "distance": _DT_DISTANCE,
    "open": _DT_OPEN,
    "repeat_until_steps_cmplt": _DT_REPEAT,
}

_INTENSITY_INT: dict[int, str] = {
    0: "active",
    1: "rest",
    2: "warmup",
    3: "cooldown",
    4: "recovery",
    5: "interval",
    6: "other",
}
_INTENSITY_STR: dict[str, str] = {v: v for v in _INTENSITY_INT.values()}

_SPORT_STR: dict[str, str] = {
    "running": "Run",
    "run": "Run",
    "cycling": "Ride",
    "bike": "Ride",
    "biking": "Ride",
    "ride": "Ride",
    "swimming": "Swim",
    "swim": "Swim",
}

_ZONE_RE = re.compile(r"Zone\s*([1-5XYxy])", re.IGNORECASE)


@dataclass
class _RawStep:
    idx: int  # sequential message position (0-based)
    duration_type: int
    duration_value: float  # s (time) | m (distance) | loop-back idx (repeat)
    target_value: int  # repeat count when duration_type == _DT_REPEAT
    intensity: int
    notes: str | None


def _int_field(frame: fitdecode.FitDataMessage, name: str, default: int = 0) -> int:
    try:
        val = frame.get_value(name)
    except Exception:
        return default
    if val is None:
        return default
    if isinstance(val, int):
        return val
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _float_field(frame: fitdecode.FitDataMessage, name: str, default: float = 0.0) -> float:
    try:
        val = frame.get_value(name)
    except Exception:
        return default
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _str_field(frame: fitdecode.FitDataMessage, name: str) -> str | None:
    try:
        val = frame.get_value(name)
    except Exception:
        return None
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _decode_duration_type(frame: fitdecode.FitDataMessage) -> int:
    val = _str_field(frame, "duration_type")
    if val is None:
        return _int_field(frame, "duration_type")
    if val.isdigit():
        return int(val)
    return _DURATION_TYPE_STR.get(val.lower(), 0)


def _decode_intensity(frame: fitdecode.FitDataMessage) -> int:
    raw: Any
    try:
        raw = frame.get_value("intensity")
    except Exception:
        return 0
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    s = str(raw).lower().strip()
    # might come back as enum name string
    reverse = {v: k for k, v in _INTENSITY_INT.items()}
    if s in reverse:
        return reverse[s]
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def _parse_zone(notes: str | None) -> str | None:
    if not notes:
        return None
    m = _ZONE_RE.search(notes)
    if not m:
        return None
    token = m.group(1).upper()
    return f"Zone {token}"


def _convert_raw(raw: _RawStep) -> Step:
    zone = _parse_zone(raw.notes)
    intensity = _INTENSITY_INT.get(raw.intensity, "active")
    if raw.duration_type == _DT_TIME:
        return Step(
            kind="time", value=float(raw.duration_value), zone_8020=zone, intensity=intensity
        )
    if raw.duration_type == _DT_DISTANCE:
        # ROADMAP §0.4: duration_value for distance steps is in meters.
        # Verify on a real file — it may be cm on some firmware versions.
        return Step(
            kind="distance", value=float(raw.duration_value), zone_8020=zone, intensity=intensity
        )
    return Step(kind="open", value=0.0, zone_8020=zone, intensity=intensity)


def _build_tree(raw_steps: list[_RawStep]) -> list[Element]:
    """Build nested workout tree from a flat list of raw FIT workout steps.

    Repeat steps (duration_type=6) consume prior steps back to the loop-back
    index, replacing them with a RepeatBlock. This handles nested repeats
    because inner RepeatBlocks are present in the result list when an outer
    repeat instruction is processed.
    """
    result: list[Element] = []
    result_raw_idx: list[int] = []  # parallel: original raw index per result entry

    for raw in raw_steps:
        if raw.duration_type == _DT_REPEAT:
            loop_back = int(raw.duration_value)
            count = raw.target_value

            # Find the first result entry whose original idx >= loop_back.
            body_start = len(result)
            for k, ridx in enumerate(result_raw_idx):
                if ridx >= loop_back:
                    body_start = k
                    break

            body = list(result[body_start:])
            result = result[:body_start]
            result_raw_idx = result_raw_idx[:body_start]

            result.append(RepeatBlock(count=count, children=body))
            result_raw_idx.append(raw.idx)
        else:
            zone = _parse_zone(raw.notes)
            if zone is None and raw.duration_type not in (_DT_OPEN,):
                intensity_str = _INTENSITY_INT.get(raw.intensity, "active")
                if intensity_str not in ("rest", "recovery", "warmup", "cooldown"):
                    logger.warning(
                        "Step %d: no zone found in notes %r — defaulting to Z1", raw.idx, raw.notes
                    )
            result.append(_convert_raw(raw))
            result_raw_idx.append(raw.idx)

    return result


def _read_fit(fit_file: Path) -> tuple[str, str | None, list[_RawStep]]:
    """Return (workout_name, sport_str_or_None, raw_steps) from a FIT file."""
    workout_name = fit_file.stem
    sport: str | None = None
    raw_steps: list[_RawStep] = []
    step_seq = 0  # sequential counter used when message_index is unavailable

    with fitdecode.FitReader(str(fit_file)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue

            if frame.name == "workout":
                name_val = _str_field(frame, "wkt_name")
                if name_val:
                    workout_name = name_val.replace("RCl", "RCI")
                sport_val = _str_field(frame, "sport")
                if sport_val:
                    sport = sport_val.lower()

            elif frame.name == "workout_step":
                # Use message_index if available, else sequential position.
                idx = _int_field(frame, "message_index", default=step_seq)
                raw_steps.append(
                    _RawStep(
                        idx=idx,
                        duration_type=_decode_duration_type(frame),
                        duration_value=_float_field(frame, "duration_value"),
                        target_value=_int_field(frame, "target_value"),
                        intensity=_decode_intensity(frame),
                        notes=_str_field(frame, "notes"),
                    )
                )
                step_seq += 1

    return workout_name, sport, raw_steps


def _detect_sport_from_path(fit_file: Path) -> str:
    """Infer sport from directory name (run/bike/swim)."""
    parts = [p.lower() for p in fit_file.parts]
    for part in reversed(parts):
        if "run" in part:
            return "Run"
        if "bike" in part or "cycling" in part or "ride" in part:
            return "Ride"
        if "swim" in part:
            return "Swim"
    return "Run"


def _detect_pool_length(fit_file: Path) -> int | None:
    """Extract pool length in metres from the filename (e.g. 'SCI1 25m.FIT')."""
    m = re.search(r"(\d+)\s*m\b", fit_file.stem, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if val in (25, 50):
            return val
    return None


def parse_fit(fit_file: Path) -> Workout:
    """Parse a .FIT workout file into a Workout model."""
    name, sport_raw, raw_steps = _read_fit(fit_file)

    if sport_raw:
        sport = _SPORT_STR.get(sport_raw, _detect_sport_from_path(fit_file))
    else:
        sport = _detect_sport_from_path(fit_file)

    pool_length = _detect_pool_length(fit_file) if sport == "Swim" else None
    elements = _build_tree(raw_steps)

    return Workout(name=name, sport=sport, pool_length_m=pool_length, elements=elements)
