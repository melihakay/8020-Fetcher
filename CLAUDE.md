# CLAUDE.md

Operational guide for working in this repo. **`ROADMAP.md` is the authoritative spec** — read it
first, especially §0 (the domain gotchas). This file is the how-to-work-here layer: commands,
conventions, and the short list of things that will bite you.

## What this is

A Python package (`eticu`, CLI `eticu`) that scrapes the **free** 80/20 Endurance
workout library, converts each `.FIT` workout into a correct intervals.icu structured workout,
and uploads them into the intervals.icu workout library. Metric units only. Swims 25 m / 50 m
only. Reimplements and fixes `njg4ne/8020-intervals-icu` (TS, GPL-3.0).

Only ever use the **free public library**. Never scrape, embed, or redistribute paid 80/20
training plans.

## Stack & tooling

- Python **3.12+**, **uv** for env/deps, `src/` layout.
- `ruff` (lint + format), `mypy --strict`, `pytest` (+ `respx` for HTTP mocking).
- Runtime deps (see ROADMAP §1): a FIT decoder (`garmin-fit-sdk` or `fitdecode`), `httpx`,
  `selectolax`/`beautifulsoup4`, `typer`, `pydantic` + `pydantic-settings`.

## Commands

```bash
uv sync                       # install (creates .venv, resolves lockfile)
uv run eticu --help    # CLI
uv run eticu all --dry-run          # full pipeline, no network writes
uv run eticu all --cycling-power     # rides as Power targets; run/swim stay HR

uv run pytest -q              # tests
uv run ruff check .           # lint
uv run ruff format .          # format
uv run mypy src               # typecheck
uv build                      # build wheel/sdist

uv add <pkg>                  # add runtime dep
uv add --dev <pkg>            # add dev dep
```

Run `ruff check`, `ruff format`, `mypy src`, and `pytest` before considering any change done.

## Layout

```
src/eticu/  models.py zones.py scrape.py download.py
                   fit_parse.py convert.py intervals_client.py upload.py cli.py
tests/             unit tests + fixtures/  (vendored sample .FIT + golden JSON/text)
ROADMAP.md         the spec (phases, acceptance criteria, correctness checklist)
CLAUDE.md          this file
.env.example       INTERVALS_API_KEY=, INTERVALS_ATHLETE_ID=
```

## Conventions

- Full type hints everywhere; `mypy --strict` must pass. Prefer pure functions in `zones`,
  `fit_parse`, and `convert` so they're trivially testable.
- Keep the `Workout`/`Step` model **unit-agnostic** (store seconds and meters). All unit and
  target-syntax formatting happens in `convert.py`, never in the parser.
- Golden-file testing is the backbone. Fixtures live in `tests/fixtures/`. **CCI1 is the
  canonical regression case** (ROADMAP §0.5) — it guards both the target-loss fix and the
  repeat-scoping fix, and it must pass in **both** HR mode and `--cycling-power` mode.
- **No live network calls in tests.** Mock intervals.icu with `respx`; use vendored `.FIT`
  fixtures rather than hitting 8020's site. Never commit an API key or real athlete ID.
- Conventional Commits; small, phase-aligned PRs that each leave the suite green.

## Domain gotchas (full detail in ROADMAP §0 — do not re-derive)

- **Targets aren't in the FIT.** Steps use `target_type = open`; the zone is in the `notes`
  string. Reading the file's target field gives you Z1 for everything — that's the bug. (§0.1)
- **Zone map inserts X and Y:** 80/20 `1,2,X,3,Y,4,5` → intervals.icu `Z1..Z7`, so **80/20
  Zone 3 → Z4**. Assert this. (§0.2)
- **Repeats scope to the loop-back index only.** The repeat step names the message index to
  return to; the `Nx` block wraps exactly that range up to the repeat instruction — steps after
  it are siblings, not children. (§0.5)
- **Metric only.** Run/Ride distance → km; swim → meters (25 m increments). No `mi`, no `y`. (§0.6)
- **Swim 25 m / 50 m only**, never 25 y; each yields a name-suffixed workout. (§0.7)
- **Target type by sport:** Run/Swim always HR; Ride HR by default, **Power** under
  `--cycling-power` (needs the athlete's FTP/Power zones; the Zwift/ERG use case). Same
  Z-number mapping for both. (§0.3)
- **Folders are flat and fixed-named:** `80/20 - Run`, `80/20 - Bike`, `80/20 - Swim`
  (intervals.icu doesn't nest folders; note "Bike" label vs `Ride` type). (§0.8)
- **Idempotent uploads:** re-running must not duplicate folders or workouts — look up by name,
  then update or skip. (Phase 4)

## Config & secrets

Read `INTERVALS_API_KEY` and `INTERVALS_ATHLETE_ID` from the environment via
`pydantic-settings` (`.env` locally, never committed — ship `.env.example`). Auth is HTTP Basic:
username literal `API_KEY`, password = the key; athlete ID goes in the path
(`https://intervals.icu/api/v1/athlete/{id}/...`). Verify exact endpoints and the bulk-upsert
semantics against `https://intervals.icu/api-docs.html` before relying on them.

## Etiquette

Be a good citizen of both services: resumable downloads (skip existing, atomic writes), modest
concurrency and a small delay when scraping 8020, and idempotent writes to intervals.icu. Prefer
a `--dry-run` path for anything that mutates the remote library.