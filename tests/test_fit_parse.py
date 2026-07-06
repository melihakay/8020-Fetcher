"""FIT parser tests.

The golden structural test (CCI1) requires tests/fixtures/CCI1.FIT.
Run 'python tests/download_fixtures.py' to fetch it, then commit the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eticu.fit_parse import _DT_REPEAT, _DT_TIME, _build_tree, _parse_zone, _RawStep
from eticu.models import RepeatBlock, Step

_FIXTURE_DIR = Path(__file__).parent / "fixtures"
_CCI1 = _FIXTURE_DIR / "CCI1.FIT"


# ---------------------------------------------------------------------------
# Zone parsing from notes field
# ---------------------------------------------------------------------------


def test_parse_zone_zone1() -> None:
    assert _parse_zone("Zone 1") == "Zone 1"
    assert _parse_zone("Zone 1 - keep it easy") == "Zone 1"


def test_parse_zone_crossover() -> None:
    assert _parse_zone("Zone X") == "Zone X"
    assert _parse_zone("Zone Y crossover") == "Zone Y"


def test_parse_zone_none_on_empty() -> None:
    assert _parse_zone(None) is None
    assert _parse_zone("") is None
    assert _parse_zone("no zone here") is None


def test_parse_zone_case_insensitive() -> None:
    assert _parse_zone("zone 3") == "Zone 3"
    assert _parse_zone("ZONE X") == "Zone X"


# ---------------------------------------------------------------------------
# _build_tree: CCI1 golden structure (constructed directly, no .FIT file)
# ---------------------------------------------------------------------------


def _cci1_raw() -> list[_RawStep]:
    """Build the raw step list matching ROADMAP §0.5."""
    T, R = _DT_TIME, _DT_REPEAT

    def s(idx: int, dt: int, dv: float, tv: int, inten: int, notes: str | None) -> _RawStep:
        return _RawStep(
            idx=idx,
            duration_type=dt,
            duration_value=dv,
            target_value=tv,
            intensity=inten,
            notes=notes,
        )

    return [
        s(0, T, 300.0, 0, 2, "Zone 1"),  # warmup
        s(1, T, 1200.0, 0, 0, "Zone 2"),  # 20m Z2
        s(2, T, 300.0, 0, 0, "Zone 3"),  # 5m Z3
        s(3, T, 180.0, 0, 4, "Zone 1"),  # 3m recovery
        s(4, R, 2, 3, 0, None),  # repeat(loop_back=2, count=3)
        s(5, T, 300.0, 0, 0, "Zone 2"),  # 5m Z2
        s(6, T, 360.0, 0, 3, "Zone 1"),  # 6m cooldown
    ]


def test_cci1_tree_length() -> None:
    tree = _build_tree(_cci1_raw())
    assert len(tree) == 5  # warmup, zone2, 3x-block, zone2, cooldown


def test_cci1_tree_repeat_block_position() -> None:
    tree = _build_tree(_cci1_raw())
    assert isinstance(tree[2], RepeatBlock)


def test_cci1_repeat_count() -> None:
    tree = _build_tree(_cci1_raw())
    block = tree[2]
    assert isinstance(block, RepeatBlock)
    assert block.count == 3


def test_cci1_repeat_block_has_two_children() -> None:
    tree = _build_tree(_cci1_raw())
    block = tree[2]
    assert isinstance(block, RepeatBlock)
    assert len(block.children) == 2


def test_cci1_repeat_children_zones() -> None:
    tree = _build_tree(_cci1_raw())
    block = tree[2]
    assert isinstance(block, RepeatBlock)
    c0, c1 = block.children
    assert isinstance(c0, Step)
    assert isinstance(c1, Step)
    assert c0.zone_8020 == "Zone 3"
    assert c1.zone_8020 == "Zone 1"


def test_cci1_repeat_children_durations() -> None:
    tree = _build_tree(_cci1_raw())
    block = tree[2]
    assert isinstance(block, RepeatBlock)
    c0, c1 = block.children
    assert isinstance(c0, Step)
    assert isinstance(c1, Step)
    assert c0.value == pytest.approx(300.0)  # 5 min
    assert c1.value == pytest.approx(180.0)  # 3 min


def test_cci1_post_repeat_steps_are_siblings() -> None:
    """Steps 5 and 6 must be siblings of the repeat, not inside it."""
    tree = _build_tree(_cci1_raw())
    assert isinstance(tree[3], Step)
    assert isinstance(tree[4], Step)
    assert tree[3].zone_8020 == "Zone 2"  # type: ignore[union-attr]
    assert tree[4].zone_8020 == "Zone 1"  # type: ignore[union-attr]
    assert tree[4].intensity == "cooldown"  # type: ignore[union-attr]


def test_cci1_warmup_step() -> None:
    tree = _build_tree(_cci1_raw())
    s = tree[0]
    assert isinstance(s, Step)
    assert s.zone_8020 == "Zone 1"
    assert s.value == pytest.approx(300.0)
    assert s.intensity == "warmup"


# ---------------------------------------------------------------------------
# Golden structural test against real CCI1.FIT (requires fixture)
# ---------------------------------------------------------------------------


_SKIP_NO_CCI1 = pytest.mark.skipif(
    not _CCI1.exists(), reason="CCI1.FIT fixture not present — run tests/download_fixtures.py"
)


@_SKIP_NO_CCI1
def test_cci1_fit_file_structural() -> None:
    from eticu.fit_parse import parse_fit

    workout = parse_fit(_CCI1)
    assert workout.sport == "Ride"
    assert len(workout.elements) == 5
    block = workout.elements[2]
    assert isinstance(block, RepeatBlock)
    assert block.count == 3
    assert len(block.children) == 2
    c0, c1 = block.children
    assert isinstance(c0, Step) and c0.zone_8020 == "Zone 3"
    assert isinstance(c1, Step) and c1.zone_8020 == "Zone 1"
