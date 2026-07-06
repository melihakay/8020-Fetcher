"""intervals.icu API client.

Auth:  HTTP Basic — username literal "API_KEY", password = your API key.
Base:  https://intervals.icu/api/v1/athlete/{athlete_id}

Folder/workout management:
  GET  .../folders          → list all folders (each may include workouts)
  POST .../folders          → create folder  {"name": "..."}
  POST .../workouts         → create workout  {name, description, type, folder_id}
  PUT  .../workouts/{id}    → update workout

Idempotency: look up by exact name before creating; update or skip on re-run.

NOTE: Verify exact endpoint paths and response shapes against
      https://intervals.icu/api-docs.html before relying on them.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://intervals.icu/api/v1/athlete/{athlete_id}"


class IntervalsClient:
    def __init__(self, api_key: str, athlete_id: str) -> None:
        self._athlete_id = athlete_id
        self._base = _BASE.format(athlete_id=athlete_id)
        # Basic auth: username = literal "API_KEY", password = the key.
        self._auth = ("API_KEY", api_key)
        self._client = httpx.Client(auth=self._auth, timeout=30.0)
        self._workouts_by_folder: dict[int, list[dict[str, Any]]] | None = None

    # ------------------------------------------------------------------
    # Folders
    # ------------------------------------------------------------------

    def list_folders(self) -> list[dict[str, Any]]:
        """Return all workout library folders."""
        r = self._client.get(f"{self._base}/folders")
        r.raise_for_status()
        data = r.json()
        # API may return a list directly or wrapped in a key.
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("folders", [])  # type: ignore[no-any-return]
        return []

    def ensure_folder(self, name: str, folder_type: str = "FOLDER") -> int:
        """Return the folder id for *name*, creating it if needed.
        
        folder_type can be 'FOLDER' (default) or 'PLAN'.
        """
        for folder in self.list_folders():
            if folder.get("name") == name:
                folder_id: int = folder["id"]
                logger.debug("Folder/Plan %r exists (id=%s)", name, folder_id)
                return folder_id
        payload = {"name": name, "type": folder_type}
        r = self._client.post(f"{self._base}/folders", json=payload)
        r.raise_for_status()
        new_id: int = r.json()["id"]
        logger.info("Created %s %r (id=%s)", folder_type, name, new_id)
        return new_id

    # ------------------------------------------------------------------
    # Workouts
    # ------------------------------------------------------------------

    def list_workouts_in_folder(self, folder_id: int) -> list[dict[str, Any]]:
        """Return workouts belonging to *folder_id*."""
        if self._workouts_by_folder is None:
            r = self._client.get(f"{self._base}/workouts")
            r.raise_for_status()
            workouts: list[dict[str, Any]] = r.json()
            self._workouts_by_folder = {}
            for w in workouts:
                fid = w.get("folder_id")
                if fid is not None:
                    self._workouts_by_folder.setdefault(fid, []).append(w)
        return self._workouts_by_folder.get(folder_id, [])

    def create_workout(
        self,
        *,
        name: str,
        description: str,
        sport: str,
        folder_id: int,
        pool_length_m: int | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": sport,
            "folder_id": folder_id,
        }
        if pool_length_m is not None:
            payload["pool_size"] = pool_length_m
        if days is not None:
            payload["day"] = days
        r = self._client.post(f"{self._base}/workouts", json=payload)
        r.raise_for_status()
        result: dict[str, Any] = r.json()
        if self._workouts_by_folder is not None:
            self._workouts_by_folder.setdefault(folder_id, []).append(result)
        logger.info("Created workout %r (id=%s, days=%s)", name, result.get("id"), days)
        return result

    def update_workout(
        self,
        workout_id: int,
        *,
        name: str,
        description: str,
        sport: str,
        pool_length_m: int | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": sport,
        }
        if pool_length_m is not None:
            payload["pool_size"] = pool_length_m
        if days is not None:
            payload["day"] = days
        r = self._client.put(f"{self._base}/workouts/{workout_id}", json=payload)
        r.raise_for_status()
        result: dict[str, Any] = r.json()
        if self._workouts_by_folder is not None:
            fid = result.get("folder_id")
            if fid is not None:
                lst = self._workouts_by_folder.get(fid, [])
                for i, w in enumerate(lst):
                    if w.get("id") == workout_id:
                        lst[i] = result
                        break
        logger.info("Updated workout %r (id=%s)", name, workout_id)
        return result

    def upsert_workout(
        self,
        *,
        name: str,
        description: str,
        sport: str,
        folder_id: int,
        pool_length_m: int | None = None,
        days: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create or update a workout by name within a folder.

        Returns (action, workout_dict) where action is 'created', 'updated',
        or 'skipped' (description unchanged).
        """
        existing = {w["name"]: w for w in self.list_workouts_in_folder(folder_id)}
        if name in existing:
            w = existing[name]
            # Skip if description and days match
            w_days = w.get("days")
            if w.get("description") == description and w_days == days:
                logger.debug("Workout %r unchanged — skipping", name)
                return "skipped", w
            result = self.update_workout(
                w["id"],
                name=name,
                description=description,
                sport=sport,
                pool_length_m=pool_length_m,
                days=days,
            )
            return "updated", result
        result = self.create_workout(
            name=name,
            description=description,
            sport=sport,
            folder_id=folder_id,
            pool_length_m=pool_length_m,
            days=days,
        )
        return "created", result

    def create_event(
        self,
        *,
        name: str,
        description: str,
        sport: str,
        start_date_local: str,
        pool_length_m: int | None = None,
    ) -> dict[str, Any]:
        """Create a calendar event directly."""
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": sport,
            "category": "WORKOUT",
            "start_date_local": start_date_local,
        }
        if pool_length_m is not None:
            payload["pool_size"] = pool_length_m
        r = self._client.post(f"{self._base}/events", json=payload)
        r.raise_for_status()
        result: dict[str, Any] = r.json()
        logger.info("Created event %r on %s (id=%s)", name, start_date_local, result.get("id"))
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> IntervalsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
