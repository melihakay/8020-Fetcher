"""Tests for IntervalClient using respx mocks — no live network calls."""

from __future__ import annotations

import httpx
import pytest
import respx

from eticu.intervals_client import IntervalsClient

_BASE = "https://intervals.icu/api/v1/athlete/i12345"


@pytest.fixture
def client() -> IntervalsClient:
    return IntervalsClient(api_key="test-key", athlete_id="i12345")


# ---------------------------------------------------------------------------
# Folder management
# ---------------------------------------------------------------------------


@respx.mock
def test_ensure_folder_creates_when_missing(client: IntervalsClient) -> None:
    respx.get(f"{_BASE}/folders").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{_BASE}/folders").mock(
        return_value=httpx.Response(201, json={"id": 42, "name": "80/20 - Run"})
    )

    folder_id = client.ensure_folder("80/20 - Run")
    assert folder_id == 42


@respx.mock
def test_ensure_folder_reuses_existing(client: IntervalsClient) -> None:
    existing = [{"id": 99, "name": "80/20 - Run", "workouts": []}]
    respx.get(f"{_BASE}/folders").mock(return_value=httpx.Response(200, json=existing))

    folder_id = client.ensure_folder("80/20 - Run")
    assert folder_id == 99
    # No POST should have been made
    assert not any(r.request.method == "POST" for r in respx.calls)


@respx.mock
def test_ensure_folder_does_not_create_duplicate(client: IntervalsClient) -> None:
    existing = [{"id": 7, "name": "80/20 - Bike", "workouts": []}]
    respx.get(f"{_BASE}/folders").mock(return_value=httpx.Response(200, json=existing))

    folder_id = client.ensure_folder("80/20 - Bike")
    assert folder_id == 7


# ---------------------------------------------------------------------------
# Workout upsert
# ---------------------------------------------------------------------------


@respx.mock
def test_upsert_creates_new_workout(client: IntervalsClient) -> None:
    respx.get(f"{_BASE}/workouts").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{_BASE}/workouts").mock(
        return_value=httpx.Response(201, json={"id": 55, "name": "CRI1"})
    )

    action, result = client.upsert_workout(
        name="CRI1",
        description="- 8020/Z1 10m Z1 HR",
        sport="Run",
        folder_id=10,
    )
    assert action == "created"
    assert result["id"] == 55


@respx.mock
def test_upsert_skips_unchanged_workout(client: IntervalsClient) -> None:
    desc = "- 8020/Z1 10m Z1 HR"
    workouts_resp = [{"id": 55, "name": "CRI1", "description": desc, "folder_id": 10}]
    respx.get(f"{_BASE}/workouts").mock(return_value=httpx.Response(200, json=workouts_resp))

    action, _ = client.upsert_workout(name="CRI1", description=desc, sport="Run", folder_id=10)
    assert action == "skipped"


@respx.mock
def test_upsert_updates_changed_workout(client: IntervalsClient) -> None:
    old_desc = "- 8020/Z1 10m Z1 HR"
    new_desc = "- 8020/Z2 10m Z2 HR"
    workouts_resp = [{"id": 55, "name": "CRI1", "description": old_desc, "folder_id": 10}]
    respx.get(f"{_BASE}/workouts").mock(return_value=httpx.Response(200, json=workouts_resp))
    respx.put(f"{_BASE}/workouts/55").mock(
        return_value=httpx.Response(200, json={"id": 55, "name": "CRI1", "description": new_desc})
    )

    action, result = client.upsert_workout(
        name="CRI1", description=new_desc, sport="Run", folder_id=10
    )
    assert action == "updated"
