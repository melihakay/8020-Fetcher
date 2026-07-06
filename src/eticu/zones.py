from __future__ import annotations

# 80/20 zone sequence including crossover zones X and Y.
# The position in this list (1-indexed) is the intervals.icu zone number.
ZONE_8020_SEQUENCE = ["Zone 1", "Zone 2", "Zone X", "Zone 3", "Zone Y", "Zone 4", "Zone 5"]

# Map from 80/20 zone name -> intervals.icu zone number (1-7).
# Key fact: "Zone 3" -> 4 because Zone X sits between Zone 2 and Zone 3.
ZONE_TO_ICU: dict[str, int] = {name: i + 1 for i, name in enumerate(ZONE_8020_SEQUENCE)}

# Fallback for unrecognized or missing zones (Z1 is the safe easy default).
FALLBACK_ICU_ZONE = 1


def map_zone(zone_8020: str | None) -> int:
    """Return intervals.icu zone number (1-7) for a given 80/20 zone name.

    Zone 3 maps to Z4 (not Z3) because Zone X inserts between 2 and 3.
    """
    if zone_8020 is None:
        return FALLBACK_ICU_ZONE
    return ZONE_TO_ICU.get(zone_8020, FALLBACK_ICU_ZONE)


def icu_zone_label(zone_8020: str | None) -> str:
    """Return 'Z1'..'Z7' for the given 80/20 zone name."""
    return f"Z{map_zone(zone_8020)}"


def step_label(zone_8020: str | None) -> str:
    """Return the step cue label shown to the athlete, e.g. '8020/Z3'.

    Uses the 80/20 zone token (1,2,X,3,Y,4,5), not the mapped ICU zone.
    """
    if zone_8020 is None:
        return "8020/Z1"
    token = zone_8020.split()[-1]  # "1", "2", "X", "3", "Y", "4", "5"
    return f"8020/Z{token}"
