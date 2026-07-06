"""Tests for the 80/20 → intervals.icu zone mapping."""

from eticu.zones import ZONE_TO_ICU, icu_zone_label, map_zone, step_label


def test_full_zone_sequence() -> None:
    expected = {
        "Zone 1": 1,
        "Zone 2": 2,
        "Zone X": 3,
        "Zone 3": 4,  # THE KEY MAPPING: 80/20 Zone 3 → ICU Z4
        "Zone Y": 5,
        "Zone 4": 6,
        "Zone 5": 7,
    }
    assert expected == ZONE_TO_ICU


def test_zone3_maps_to_z4() -> None:
    # ROADMAP §0.2 explicitly requires this assertion.
    assert map_zone("Zone 3") == 4
    assert icu_zone_label("Zone 3") == "Z4"


def test_zone_x_maps_to_z3() -> None:
    assert map_zone("Zone X") == 3
    assert icu_zone_label("Zone X") == "Z3"


def test_zone_y_maps_to_z5() -> None:
    assert map_zone("Zone Y") == 5
    assert icu_zone_label("Zone Y") == "Z5"


def test_zone1_maps_to_z1() -> None:
    assert map_zone("Zone 1") == 1


def test_zone5_maps_to_z7() -> None:
    assert map_zone("Zone 5") == 7


def test_none_zone_returns_fallback() -> None:
    assert map_zone(None) == 1
    assert icu_zone_label(None) == "Z1"


def test_unknown_zone_returns_fallback() -> None:
    assert map_zone("Zone 99") == 1


def test_step_label_tokens() -> None:
    assert step_label("Zone 1") == "8020/Z1"
    assert step_label("Zone X") == "8020/ZX"
    assert step_label("Zone 3") == "8020/Z3"
    assert step_label("Zone Y") == "8020/ZY"
    assert step_label(None) == "8020/Z1"
