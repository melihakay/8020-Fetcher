from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    kind: str  # "time" | "distance" | "open"
    value: float  # seconds (time), meters (distance), 0.0 (open)
    zone_8020: str | None  # "Zone 1","Zone 2","Zone X","Zone 3","Zone Y","Zone 4","Zone 5"
    intensity: str  # "active"|"rest"|"warmup"|"cooldown"|"recovery"|"interval"|"other"


@dataclass
class RepeatBlock:
    count: int
    children: list[Step | RepeatBlock] = field(default_factory=list)


Element = Step | RepeatBlock


@dataclass
class Workout:
    name: str
    sport: str  # "Run" | "Ride" | "Swim"
    pool_length_m: int | None  # only for Swim
    elements: list[Element]
