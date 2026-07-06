# Roadmap — `eticu`: 80/20 Endurance → intervals.icu (Python)

A build plan for Claude Code. Implement a Python package that scrapes the **free** 80/20
Endurance workout library, converts each `.FIT` workout into a correct intervals.icu
structured workout, and uploads them into an intervals.icu **workout library** (folders).
All units **metric**. Swims **25 m and 50 m only** (never 25 y).

> Scope note: this populates the *workout library* only. Scheduling the 16-week plan onto
> the calendar is a **separate** task and is out of scope here. Brick (`BR*`) workouts do
> not exist as `.FIT` files in the library and are also out of scope.

Prior art to learn from (TypeScript, GPL-3.0): `njg4ne/8020-intervals-icu`. We reimplement
in Python and **fix** three things it gets wrong or doesn't do: target loss on native
import, imperial units, and 25y-only swims — plus we add **idempotent** upload.

---

## 0. The domain knowledge that is easy to get wrong

This section is the point of the whole roadmap. Read it before writing any parser code.

### 0.1 How 80/20 encodes intensity in the FIT file

Each workout step in the `.FIT` uses **`target_type = open` (enum 2)** — i.e. there is **no
structured HR/power target** in the file. The intended intensity lives in the step's free-text
**`notes`** field as an 80/20 zone name: `"Zone 1"`, `"Zone 2"`, `"Zone 3"`, `"Zone 4"`,
`"Zone 5"`, and the crossover zones `"Zone X"` and `"Zone Y"`.

**Consequence:** intervals.icu's native `.FIT` workout import sees "open target" and defaults
every step to Z1. That is the bug the user observed. We must read the zone from `notes` and
emit an explicit target ourselves.

### 0.2 Zone model mapping (80/20 → intervals.icu)

80/20 uses a 7-level model with two crossover zones inserted: `1, 2, X, 3, Y, 4, 5`.
Map onto intervals.icu's `Z1..Z7` **in order**:

| 80/20 zone | intervals.icu |
|-----------|----------------|
| Zone 1    | Z1 |
| Zone 2    | Z2 |
| Zone X    | Z3 |
| **Zone 3**| **Z4** |
| Zone Y    | Z5 |
| Zone 4    | Z6 |
| Zone 5    | Z7 |

The non-obvious part: **80/20 "Zone 3" (threshold/tempo) maps to intervals.icu Z4**, because X
sits between 2 and 3. Keep the 80/20 name in the step label for the athlete to read, but set
the actual **target zone to the mapped value**. Assert this explicitly in tests.

> Prerequisite documented for the user (README): for these targets to be correct, whichever
> intervals.icu zones are used (**HR** for Run/Swim, and HR or **Power** for Ride per §0.3) must
> follow the 80/20 seven-zone layout — HR zones populated from the 80/20 calculator via LTHR,
> Power zones from FTP. The same Z-number mapping applies to both.

### 0.3 Target type by sport (configurable)

The zone→zone **number** mapping in §0.2 is identical regardless of target type — only the
target *kind* (HR vs Power) changes. Defaults and options:

- **Run / Swim → always HR.** These stay heart-rate based (as intended for 80/20).
- **Ride → HR by default, Power when opted in.** A `--cycling-power` flag (config
  `cycling_target: hr | power`, default `hr`) makes **cycling** workouts emit **Power** targets
  instead of HR, mapping the 80/20 zone to the athlete's intervals.icu **Power** zone of the
  same number (so 80/20 Zone 3 → Power **Z4**). Run/Swim are unaffected by the flag.

Unzoned steps (rare / a `notes` field that fails to parse) get an easy default (Z1–Z2) plus a
logged warning — never a silent Z1.

**Why the Power option exists (from a user request):** Zwift and other ERG-mode platforms
**ignore HR targets** in structured workouts — they need **power (%FTP)** targets to drive ERG.
With HR-only cycling workouts, the 80/20 rides can't be synced to Zwift through the
intervals.icu integration. A per-import Power option makes the whole cycling library usable in
Zwift immediately, instead of hand-flipping hundreds of workouts HR→Power. Keep the zone labels
(`8020/Z…`) in the step name either way; only the underlying target type differs.

> **Prerequisite for `--cycling-power` (README):** the athlete must have **FTP + Power zones**
> set in intervals.icu, and those Power zones should follow the 80/20 seven-zone layout so the
> mapped zone lands correctly. Without FTP, power targets are meaningless — fall back to HR and
> warn. Export sanity check: with Power targets and FTP set, an intervals.icu → Zwift/`.zwo`
> sync should render as **%FTP** ranges.

### 0.4 FIT step decoding reference (verify enums against the SDK at build time)

- `duration_type`: `0 = time` (value in **ms**), `1 = distance` (value in **m** — confirm scale
  on a real distance workout via the SDK), `5 = open`, `6 = repeat_until_steps_cmplt`.
- `intensity`: `0 = active`, `1 = rest`, `2 = warmup`, `3 = cooldown`, `4 = recovery`,
  `5 = interval`, `6 = other`.
- `target_type`: `2 = open` (what 80/20 uses). Others exist but are unused by this library.
- **Repeat step**: `duration_type = 6`; the loop-back is the **message index to return to**
  (call it `duration_step`), and the **repeat count** is carried in the target field. Decode
  both explicitly and validate against the golden case below — do **not** assume the repeat
  wraps "everything after the previous block."

### 0.5 THE GOLDEN CASE — CCI1 (make this a committed regression test)

Raw FIT steps (ground truth, taken from a real file):

| idx | duration_type | duration_value | target_type | target_value | intensity | notes  |
|-----|---------------|----------------|-------------|--------------|-----------|--------|
| 0   | 0 (time)      | 300000 (5m)    | 2 (open)    | 0            | 2 warmup  | Zone 1 |
| 1   | 0             | 1200000 (20m)  | 2           | 0            | 0 active  | Zone 2 |
| 2   | 0             | 300000 (5m)    | 2           | 0            | 0 active  | Zone 3 |
| 3   | 0             | 180000 (3m)    | 2           | 0            | 4 recovery| Zone 1 |
| 4   | 6 (repeat)    | 2 (→ idx 2)    | –           | 3 (×3)       | –         | –      |
| 5   | 0             | 300000 (5m)    | 2           | 0            | 0 active  | Zone 2 |
| 6   | 0             | 360000 (6m)    | 2           | 0            | 3 cooldown| Zone 1 |

**Correct** logical structure — the `3x` wraps **only steps 2–3** (the loop-back target through
the step before the repeat instruction). Steps 5 and 6 are **after** the repeat and are **not**
in the loop:

```
Zone 1  5m   (warmup)
Zone 2  20m
3x
    Zone 3  5m
    Zone 1  3m   (recovery)
Zone 2  5m
Zone 1  6m   (cooldown)
```

**Correct** intervals.icu workout text (metric, HR targets, 80/20 labels, note Zone 3 → Z4):

```
- 8020/Z1 5m Z1 HR
- 8020/Z2 20m Z2 HR
3x
- 8020/Z3 5m Z4 HR
- 8020/Z1 3m Z1 HR
- 8020/Z2 5m Z2 HR
- 8020/Z1 6m Z1 HR
```

CCI1 is a **cycling** workout, so it is also the fixture for the Power option (§0.3). Under
`--cycling-power`, the same workout must instead emit **Power** targets (Zone 3 → Power Z4),
with Run/Swim unaffected. Expected `--cycling-power` text (verify the exact intervals.icu
power-target syntax — power is the default target type, so it may be a bare zone or an explicit
`Power` keyword):

```
- 8020/Z1 5m Z1
- 8020/Z2 20m Z2
3x
- 8020/Z3 5m Z4
- 8020/Z1 3m Z1
- 8020/Z2 5m Z2
- 8020/Z1 6m Z1
```

The **broken** native import the user saw was `Zone N … Z1` on every line (target loss, §0.1)
**and** the `3x` mis-scoped to include steps 5–6. Both are fixed here. This single workout is
the canonical regression test for the parser (§0.5 structure) and the converter — assert **both**
the default HR text and the `--cycling-power` text.

### 0.6 Metric units

- Run / Ride distance steps: meters → **km** (never miles). Pick a rounding granularity
  (suggest nearest 0.1 km) and document it.
- Time steps: `Xh`/`Ym`/`Zs` formatting.
- Swim: keep **meters**; round to nearest 25 m. Pool length line uses the file's real length.

### 0.7 Swim pool-size selection

Library swim filenames encode pool size, e.g. `SCI1 25m.FIT`, `SCI1 50m.FIT`, `SCI1 25y.FIT`.
**Fetch and convert only `25m` and `50m`; skip `25y` entirely.** A swim workout therefore
yields up to two library entries (25 m and 50 m). Distinguish them by name suffix and set the
correct pool-length metadata on each.

### 0.8 Library folder structure — three flat "80/20 - …" folders

intervals.icu library folders are **flat — they do not nest**. Use three top-level folders with
this exact naming convention:

```
80/20 - Run
80/20 - Bike
80/20 - Swim
```

Each workout goes in the folder matching its sport (internal sport type `Run` → `80/20 - Run`,
`Ride` → `80/20 - Bike`, `Swim` → `80/20 - Swim`). Note the folder label is **"Bike"** even
though the intervals.icu workout `type` is `Ride`.

Folder creation must be **idempotent**: look up existing folders by exact name before creating,
and reuse them (see Phase 4). No `folder_layout` option is needed — the naming is fixed.

---

## 1. Package shape & tooling

- Manager: **uv**, `src/` layout, package name `eticu`, CLI entry `eticu`.
- Python 3.12+. Full type hints, `ruff` + `mypy --strict`, `pytest`.
- Config via env (`.env`, loaded with pydantic-settings): `INTERVALS_API_KEY`, `INTERVALS_ATHLETE_ID`.
  Never commit `.env`; ship `.env.example`.
- Suggested deps: `garmin-fit-sdk` **or** `fitdecode` (FIT decode — implementer chooses, prefer
  the one with cleaner repeat/message-index access; verify §0.4 enums against it), `httpx`
  (HTTP), `selectolax` or `beautifulsoup4` (HTML), `typer` (CLI), `pydantic`/`pydantic-settings`
  (models/config). Tests: `pytest`, `respx` (mock intervals.icu).

### Modules

```
src/eticu/
  models.py           # Step, RepeatBlock, Workout dataclasses/pydantic models
  zones.py            # 80/20 <-> ICU zone maps + label helpers (§0.2)
  scrape.py           # discover workout URLs from the library page, grouped by sport
  download.py         # download .FIT to cache; swim filter 25m/50m; resumable
  fit_parse.py        # .FIT -> Workout model (CORE correctness: §0.1, §0.4, §0.5)
  convert.py          # Workout -> intervals.icu text (metric; HR or Power target; repeats) (§0.3, §0.5, §0.6)
  intervals_client.py # API: auth, folders (flat, named §0.8), list workouts, bulk upsert
  upload.py           # orchestrate "80/20 - …" folders + idempotent upload (§0.8)
  cli.py              # typer app: scrape / download / convert / upload / all
                      #   flags: --dry-run, --cycling-power, --cache-dir
```

### Data model (`models.py`)

- `Step(kind: "time"|"distance", value: seconds|meters, zone_8020: str|None, intensity: str)`
- `RepeatBlock(count: int, children: list[Step|RepeatBlock])` — support **nested** repeats.
- `Workout(name, sport: "Run"|"Ride"|"Swim", pool_length_m: int|None, elements: list[...])`
- Keep the model unit-agnostic (store seconds/meters); unit formatting happens in `convert.py`.

---

## 2. Milestones

Each phase is independently shippable and testable. Do them in order; gate each on its
acceptance criteria.

### Phase 0 — Scaffolding
`uv init`, layout, lint/type/test config, minimal CI (GitHub Actions: ruff, mypy, pytest).
**Done when:** `uv run pytest` runs green on an empty suite; CI passes.

### Phase 1 — FIT parser + models + golden structural test
Implement `models.py` and `fit_parse.py`. Decode time/distance/open/repeat steps; read zone
from `notes`; build nested `RepeatBlock`s using the loop-back index (§0.4).
**Done when:** parsing the committed CCI1 fixture yields exactly the §0.5 structure — a `3x`
block containing **only** the two steps (Zone 3 5m, Zone 1 3m), with Zone 2 5m and Zone 1 6m as
siblings **after** it. Add fixtures for a distance-based run and a swim; assert distances/units.

### Phase 2 — Zones + converter (golden text test, both target modes)
Implement `zones.py` (§0.2) and `convert.py` (metric, intensity tags, repeat syntax, and a
`target: hr | power` parameter per §0.3). Run/Swim always HR; Ride HR by default, Power when
requested.
**Done when:** converting CCI1 (a Ride) produces the exact §0.5 **HR** text by default *and* the
exact **Power** text under power mode (assert 80/20 Zone 3 → `Z4` in both, Zone 1 → `Z1`,
Zone 2 → `Z2`; HR mode ends every step in `HR`, power mode does not; no `mi`/`y` anywhere).
Confirm a Run fixture stays HR regardless of the flag. Unzoned step → easy default + warning.

### Phase 3 — Scraper + downloader
`scrape.py` enumerates run/bike/swim workout URLs from the library page; `download.py` caches
`.FIT` files, is resumable (skip existing, atomic writes), and applies the **25m/50m-only**
swim filter (§0.7).
**Done when:** a dry-run lists the expected counts per sport; swim set contains only 25m/50m;
re-running downloads nothing new.

### Phase 4 — intervals.icu client + idempotent upload
`intervals_client.py`: Basic auth (username `API_KEY`, password = the key), athlete id in path,
base `https://intervals.icu/api/v1/athlete/{id}`. Create the three flat folders **`80/20 - Run`
/ `80/20 - Bike` / `80/20 - Swim`** (§0.8), reusing any that already exist by exact name. **List
existing library workouts**, and upsert. Verify bulk endpoint + upsert semantics against the API
docs (see §3) — implement true idempotency: match by name within folder, then update or skip
instead of blind-inserting (fixes the reference repo's duplicate-on-rerun behavior).
**Done when:** first run creates the three folders + N workouts; second run creates **zero**
duplicate folders or workouts (updates or skips). Client tests use `respx` mocks — no live calls
in CI.

### Phase 5 — CLI + end-to-end
`typer` app with `scrape`, `download`, `convert`, `upload`, and `all`; flags `--dry-run`,
`--cache-dir`, and **`--cycling-power`** (§0.3). `all` runs the full pipeline from empty cache to
populated library.
**Done when:** `eticu all --dry-run` prints a full plan without network writes;
`eticu all` populates the library end-to-end; `eticu all --cycling-power` yields
power-targeted rides while runs/swims stay HR.

### Phase 6 — Docs + release
README covering: install, env setup, the **zone prerequisite** (§0.2 note) + LTHR guidance, the
**`--cycling-power` option** and its **FTP/Power-zone prerequisite + Zwift/ERG rationale**
(§0.3), the **"80/20" folder layout** (§0.8), metric/swim behavior, and out-of-scope items
(calendar plan, bricks). Package build with uv, tag-driven version, GH Actions release.
License-compatibly credit the reference repo.

---

## 3. Verification & open decisions for the implementer

- Confirm FIT `duration_value` scale for **distance** steps against the SDK on a real distance
  workout before trusting meters (§0.4).
- intervals.icu API: confirm the bulk workouts endpoint and whether it upserts by id or always
  inserts; design idempotency accordingly. Docs: `https://intervals.icu/api-docs.html` and the
  intervals.icu forum. (Reference repo used `POST /folders` and `POST /workouts/bulk`.)
- Decide km rounding granularity (§0.6). Swim 25m/50m variants are separate workouts (name-suffixed),
  both in the `80/20 - Swim` folder (§0.7, §0.8).
- Decide whether to emit workouts as plain-text `description` (simplest, matches prior art) or as
  a structured `workout_doc` JSON. Start with text; the golden test targets text.
- **Power-target syntax (§0.3):** confirm how intervals.icu's workout text marks a Power target
  vs HR (bare zone, explicit `Power`, or `%FTP` range) and pick the form that exports cleanly to
  Zwift `.zwo` as %FTP. Decide whether ERG wants a single mid-zone target or the zone range.

## 4. Correctness checklist (must all pass before release)

- [ ] `target_type = open` handled; zone read from `notes` (§0.1).
- [ ] 80/20 Zone 3 → intervals.icu **Z4**; full X/Y mapping asserted (§0.2).
- [ ] Repeat wraps exactly the loop-back range; post-repeat steps excluded (§0.5).
- [ ] Nested repeats handled.
- [ ] Run/Swim always HR; Ride HR by default and **Power** under `--cycling-power` (§0.3);
      unzoned → easy default + warning.
- [ ] Power mode requires FTP/Power zones; falls back to HR + warning when absent.
- [ ] Workouts land in the three flat folders **`80/20 - Run` / `80/20 - Bike` / `80/20 - Swim`**
      by sport (§0.8); folder creation idempotent.
- [ ] All output metric; no `mi`, no `y`; swims 25 m / 50 m only with correct pool length.
- [ ] Upload is idempotent (no duplicates on re-run).
- [ ] CCI1 passes both the structural (Phase 1) and exact-text (Phase 2) golden tests.