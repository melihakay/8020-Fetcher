"""eticu CLI — scrape / download / convert / upload / all."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Convert 80/20 Endurance workouts to intervals.icu structured workouts.")

_DEFAULT_CACHE = Path("8020_cache")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s", stream=sys.stderr)


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------


@app.command()
def scrape(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List all .FIT URLs from the 80/20 workout library (no download)."""
    _setup_logging(verbose)
    from eticu.scrape import scrape_workout_urls

    grouped = scrape_workout_urls()
    for sport, urls in grouped.items():
        for url in urls:
            typer.echo(f"{sport}\t{url}")
    total = sum(len(v) for v in grouped.values())
    run, ride, swim = len(grouped["Run"]), len(grouped["Ride"]), len(grouped["Swim"])
    typer.echo(f"\nTotal: {total}  (Run={run}  Ride={ride}  Swim={swim})")


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


@app.command()
def download(
    cache_dir: Annotated[Path, typer.Option("--cache-dir")] = _DEFAULT_CACHE,
    workers: Annotated[int, typer.Option("--jobs", "-j")] = 4,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Download all .FIT files to a local cache directory."""
    _setup_logging(verbose)
    from eticu.download import download_all
    from eticu.scrape import scrape_workout_urls

    grouped = scrape_workout_urls()
    all_urls = [u for urls in grouped.values() for u in urls]
    typer.echo(f"Downloading {len(all_urls)} files to {cache_dir} ...")
    counts = download_all(all_urls, cache_dir, workers=workers, dry_run=dry_run)
    typer.echo(f"Done. ok={counts['ok']}  skip={counts['skip']}  error={counts['error']}")
    if counts["error"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


@app.command(name="convert")
def convert_cmd(
    fit_file: Annotated[Path, typer.Argument(help=".FIT file to convert")],
    cycling_power: Annotated[bool, typer.Option("--cycling-power")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Convert a single .FIT workout file and print the intervals.icu text."""
    _setup_logging(verbose)
    from eticu.convert import convert as do_convert
    from eticu.fit_parse import parse_fit

    workout = parse_fit(fit_file)
    typer.echo(do_convert(workout, cycling_power=cycling_power))


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------


@app.command()
def upload(
    cache_dir: Annotated[Path, typer.Option("--cache-dir")] = _DEFAULT_CACHE,
    cycling_power: Annotated[bool, typer.Option("--cycling-power")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Upload converted workouts to intervals.icu workout library."""
    _setup_logging(verbose)
    from eticu.config import get_settings
    from eticu.intervals_client import IntervalsClient
    from eticu.upload import upload_workouts

    settings = get_settings()
    if not settings.intervals_api_key or not settings.intervals_athlete_id:
        typer.echo("Error: INTERVALS_API_KEY and INTERVALS_ATHLETE_ID must be set.", err=True)
        raise typer.Exit(1)

    fit_files = sorted(set(cache_dir.rglob("*.FIT")) | set(cache_dir.rglob("*.fit")))
    if not fit_files:
        typer.echo(f"No .FIT files found in {cache_dir}. Run 'eticu download' first.")
        raise typer.Exit(1)

    typer.echo(f"Uploading {len(fit_files)} workout(s) ...")
    with IntervalsClient(settings.intervals_api_key, settings.intervals_athlete_id) as client:
        counts = upload_workouts(fit_files, client, cycling_power=cycling_power, dry_run=dry_run)

    typer.echo(
        f"Done. created={counts['created']}  updated={counts['updated']}  "
        f"skipped={counts['skipped']}  error={counts['error']}"
    )
    if counts["error"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# upload-plan
# ---------------------------------------------------------------------------


@app.command(name="upload-plan")
def upload_plan_cmd(
    plan_csv: Annotated[Path, typer.Argument(help="CSV file containing the plan")],
    name: Annotated[str, typer.Option("--name", "-n", help="Name of the training plan folder")],
    pool_length: Annotated[int | None, typer.Option("--pool-length", help="Pool length in meters (e.g., 25 or 50)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Upload a training plan from a CSV to intervals.icu."""
    _setup_logging(verbose)
    from eticu.config import get_settings
    from eticu.intervals_client import IntervalsClient
    from eticu.upload import upload_plan

    settings = get_settings()
    if not dry_run and (not settings.intervals_api_key or not settings.intervals_athlete_id):
        typer.echo("Error: INTERVALS_API_KEY and INTERVALS_ATHLETE_ID must be set.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Uploading plan {name!r} from {plan_csv} ...")
    if dry_run:
        typer.echo("  [DRY-RUN] Will not perform actual upload.")

    with IntervalsClient(settings.intervals_api_key, settings.intervals_athlete_id) as client:
        counts = upload_plan(
            csv_file=plan_csv,
            plan_name=name,
            client=client,
            pool_length_m=pool_length,
            dry_run=dry_run,
        )

    typer.echo(
        f"Done. created={counts['created']}  updated={counts['updated']}  "
        f"skipped={counts['skipped']}  error={counts['error']}  missing={counts['missing']}"
    )
    if counts["error"] or counts["missing"]:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------


@app.command(name="all")
def all_cmd(
    cache_dir: Annotated[Path, typer.Option("--cache-dir")] = _DEFAULT_CACHE,
    workers: Annotated[int, typer.Option("--jobs", "-j")] = 4,
    cycling_power: Annotated[bool, typer.Option("--cycling-power")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run the full pipeline: scrape → download → upload."""
    _setup_logging(verbose)
    from eticu.config import get_settings
    from eticu.download import download_all
    from eticu.intervals_client import IntervalsClient
    from eticu.scrape import scrape_workout_urls
    from eticu.upload import upload_workouts

    settings = get_settings()
    if not dry_run and (not settings.intervals_api_key or not settings.intervals_athlete_id):
        typer.echo("Error: INTERVALS_API_KEY and INTERVALS_ATHLETE_ID must be set.", err=True)
        raise typer.Exit(1)

    typer.echo("Step 1/3: Scraping workout URLs ...")
    grouped = scrape_workout_urls()
    all_urls = [u for urls in grouped.values() for u in urls]
    typer.echo(f"  Found {len(all_urls)} URLs.")

    typer.echo(f"Step 2/3: Downloading to {cache_dir} ...")
    dl = download_all(all_urls, cache_dir, workers=workers, dry_run=dry_run)
    typer.echo(f"  ok={dl['ok']}  skip={dl['skip']}  error={dl['error']}")

    fit_files = sorted(set(cache_dir.rglob("*.FIT")) | set(cache_dir.rglob("*.fit")))
    typer.echo(f"Step 3/3: Uploading {len(fit_files)} workout(s) ...")

    if dry_run:
        typer.echo("  [DRY-RUN] Skipping upload.")
        return

    with IntervalsClient(settings.intervals_api_key, settings.intervals_athlete_id) as client:
        counts = upload_workouts(fit_files, client, cycling_power=cycling_power, dry_run=dry_run)

    typer.echo(
        f"  created={counts['created']}  updated={counts['updated']}  "
        f"skipped={counts['skipped']}  error={counts['error']}"
    )
    if counts["error"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
