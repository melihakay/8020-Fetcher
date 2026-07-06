# eticu: 80/20 Endurance to Intervals.icu

`eticu` is a Python CLI pipeline that scrapes the **free** 80/20 Endurance workout library, parses and converts the `.FIT` files into fully structured [Intervals.icu](https://intervals.icu/) workouts, and idempotently uploads them to your Intervals.icu workout library.

It serves as a more robust, metric-first Python reimplementation of the [8020-intervals-icu](https://github.com/njg4ne/8020-intervals-icu) TypeScript project, completely fixing target loss issues during imports, nested repeat structures, and adding idempotent uploading.

> **Scope Note**: This tool populates the *workout library* folders only. Scheduling the 16-week plan onto your calendar is a separate task and is out of scope. Brick (`BR*`) workouts do not exist as `.FIT` files in the library and are therefore also out of scope.

## Installation & Setup

This project uses `uv` for dependency management.

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd 8020-fetcher
   ```

2. **Environment Variables:**
   Copy `.env.example` to `.env` and set your Intervals.icu credentials:
   ```env
   INTERVALS_API_KEY=your_intervals_api_key
   INTERVALS_ATHLETE_ID=your_intervals_athlete_id
   ```
   You can find these in your Intervals.icu settings.

## Usage

To run the full pipeline (scrape → download → upload):
```bash
uv run eticu all
```

**Options:**
- `--dry-run`: Do everything except network writes to Intervals.icu.
- `--cycling-power`: Emit Power targets (instead of Heart Rate) for Ride workouts. (Run and Swim always remain HR).
- `--cache-dir <dir>`: Directory to cache downloaded `.FIT` files (defaults to `8020_cache`).

To convert and view a single downloaded `.FIT` file locally:
```bash
uv run eticu convert 8020_cache/bike/CCI1.FIT
```

To upload a training plan from a CSV file (e.g. `plans/olympic_distance_level_0.csv`):
```bash
uv run eticu upload-plan plans/olympic_distance_level_0.csv --name "Olympic Level 0"
```

**Options:**
- `--pool-length`: Pool length in meters (e.g., 25 or 50) for swim workouts.
- `--dry-run`: Parse the CSV and list the plan without uploading.

## Critical Prerequisites

For the generated workouts to be accurate, you **must** configure your Intervals.icu settings to match the 80/20 Endurance methodology.

### 1. The 7-Zone Prerequisite
80/20 uses a 7-level zone system with two crossover zones: `1, 2, X, 3, Y, 4, 5`. 
Intervals.icu supports 7 zones (`Z1` to `Z7`). `eticu` maps them sequentially. 
**You MUST update your Intervals.icu HR zones (and Power zones, if using `--cycling-power`) to match the numbers from the 80/20 zone calculator.**

| 80/20 Zone | Intervals.icu Zone |
|------------|--------------------|
| Zone 1     | Z1                 |
| Zone 2     | Z2                 |
| Zone X     | Z3                 |
| **Zone 3** | **Z4**             |
| Zone Y     | Z5                 |
| Zone 4     | Z6                 |
| Zone 5     | Z7                 |

*Note: Because of crossover Zone X, 80/20's "Zone 3" maps to Intervals "Z4".*

### 2. The `--cycling-power` Option & ERG Mode
By default, 80/20 workouts use Heart Rate targets. However, platforms like **Zwift** in ERG mode ignore HR targets; they require **Power (%FTP)**.

If you ride on Zwift/TrainerRoad, pass the `--cycling-power` flag. This converts all `Ride` workouts to use Power zones.
* **Prerequisite**: For this to work, you MUST have your FTP and 7-level Power zones correctly configured in your Intervals.icu settings. If you don't, power targets will be meaningless.

## Core Behaviors

- **Metric Units**: All outputs are metric. Run and Ride distances are rounded to the nearest `0.1 km`. Swims are strictly handled in `meters` (`mtr` in Intervals.icu to distinguish from minutes). 
- **Pool Lengths**: Only `25m` and `50m` swim workouts are fetched and processed. `25y` files are skipped.
- **Folder Layout**: Workouts are uploaded into three flat folders (created automatically if they don't exist):
  - `80/20 - Run`
  - `80/20 - Bike`
  - `80/20 - Swim`
- **Idempotency**: The upload is completely idempotent. It matches workouts by exact name within the folder and skips identical workouts, preventing duplication if the script is run multiple times.

## Credits & License
This project was heavily inspired by the GPL-3.0 licensed `njg4ne/8020-intervals-icu` project, expanding its capabilities into a fully-typed Python package with deeper FIT file introspection.
