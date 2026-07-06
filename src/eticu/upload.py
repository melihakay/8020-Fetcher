"""Orchestrate upload of all 80/20 workouts to the intervals.icu workout library.

Folder layout (flat, fixed names per ROADMAP §0.8):
  80/20 - Run   ← Run workouts
  80/20 - Bike  ← Ride workouts  (note: label is "Bike", type is "Ride")
  80/20 - Swim  ← Swim workouts
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from eticu.convert import convert
from eticu.fit_parse import parse_fit
from eticu.intervals_client import IntervalsClient
from eticu.models import Workout
from eticu.plan import parse_plan_csv

logger = logging.getLogger(__name__)

_FOLDER_BY_SPORT: dict[str, str] = {
    "Run": "80/20 - Run",
    "Ride": "80/20 - Bike",
    "Swim": "80/20 - Swim",
}


def upload_workouts(
    fit_files: list[Path],
    client: IntervalsClient,
    *,
    cycling_power: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """Parse, convert, and upsert each FIT file into the correct library folder.

    Returns counts: {"created": N, "updated": N, "skipped": N, "error": N}.
    """
    counts = {"created": 0, "updated": 0, "skipped": 0, "error": 0}

    # Ensure all three folders exist (idempotent).
    folder_ids: dict[str, int] = {}
    for sport, folder_name in _FOLDER_BY_SPORT.items():
        if dry_run:
            logger.info("[DRY-RUN] Would ensure folder %r", folder_name)
            folder_ids[sport] = -1
        else:
            folder_ids[sport] = client.ensure_folder(folder_name)

    for fit_file in fit_files:
        try:
            workout: Workout = parse_fit(fit_file)
        except Exception as exc:
            logger.error("Failed to parse %s: %s", fit_file.name, exc)
            counts["error"] += 1
            continue

        description = convert(workout, cycling_power=cycling_power)
        folder_id = folder_ids[workout.sport]

        if dry_run:
            logger.info(
                "[DRY-RUN] Would upsert %r → folder %r\n%s",
                workout.name,
                _FOLDER_BY_SPORT[workout.sport],
                description,
            )
            counts["skipped"] += 1
            continue

        try:
            action, _ = client.upsert_workout(
                name=workout.name,
                description=description,
                sport=workout.sport,
                folder_id=folder_id,
                pool_length_m=workout.pool_length_m,
            )
            counts[action] += 1
        except Exception as exc:
            logger.error("Failed to upload %r: %s", workout.name, exc)
            counts["error"] += 1

    return counts

def upload_plan(
    csv_file: Path,
    plan_name: str,
    client: IntervalsClient,
    *,
    pool_length_m: int | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Parse a plan CSV, lookup workouts from the user's Intervals.icu library, and upsert them to a Plan folder.

    Returns counts: {"created": N, "updated": N, "skipped": N, "error": N, "missing": N}.
    """
    counts = {"created": 0, "updated": 0, "skipped": 0, "error": 0, "missing": 0}

    # 1. Parse CSV
    plan_entries = parse_plan_csv(csv_file)

    # 2. Build dictionary of existing workouts from library
    workout_dict: dict[str, dict[str, Any]] = {}
    library_folders = ("80/20 - Run", "80/20 - Bike", "80/20 - Swim")
    for folder in client.list_folders():
        if folder.get("name") in library_folders:
            workouts = client.list_workouts_in_folder(folder["id"])
            for w in workouts:
                clean_name = w["name"].replace("\xa0", " ").strip().lower()
                workout_dict[clean_name] = w

    # 3. Ensure Plan Folder exists
    if dry_run:
        logger.info("[DRY-RUN] Would ensure plan %r", plan_name)
        folder_id = -1
    else:
        folder_id = client.ensure_folder(plan_name, folder_type="PLAN")

    # 4. Upload each plan entry
    for entry in plan_entries:
        for wcode in entry.workout_codes:
            w_lower = wcode.lower()
            
            # Brick sessions
            if w_lower.startswith("br"):
                workout_name = f"W{entry.week:02}D{entry.day_of_week + 1} - Brick exercise - {wcode.upper()}"
                description = "Brick session"
                sport = "Other"
                w_pool_size = None
            else:
                # If it's a swim workout and we have a pool length, try matching e.g., "sci1 25m"
                if w_lower.startswith("s") and pool_length_m:
                    pool_suffix = f" {pool_length_m}m"
                    if w_lower + pool_suffix in workout_dict:
                        w_lower += pool_suffix

                if w_lower not in workout_dict:
                    logger.error("Workout %r not found in online library", wcode)
                    counts["missing"] += 1
                    continue

                workout = workout_dict[w_lower]
                description = workout.get("description", "")
                sport = workout.get("type", "Run")
                w_pool_size = workout.get("pool_size")

                # Format name: W01D1 - RF3
                workout_name = f"W{entry.week:02}D{entry.day_of_week + 1} - {workout['name']}"

            if dry_run:
                logger.info("[DRY-RUN] Would upsert %r (days=%d) to %r", workout_name, entry.days_offset, plan_name)
                counts["skipped"] += 1
                continue

            try:
                action, _ = client.upsert_workout(
                    name=workout_name,
                    description=description,
                    sport=sport,
                    folder_id=folder_id,
                    pool_length_m=w_pool_size,
                    days=entry.days_offset,
                )
                counts[action] += 1
            except Exception as exc:
                logger.error("Failed to upload %r: %s", workout_name, exc)
                counts["error"] += 1

    return counts

