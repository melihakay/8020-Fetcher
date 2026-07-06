# Test results [RESOLVED]

PS C:\Users\melih\Development\8020 Fetcher> uv run ruff check .
All checks passed!
PS C:\Users\melih\Development\8020 Fetcher> uv run ruff format .         
18 files left unchanged
PS C:\Users\melih\Development\8020 Fetcher> uv run pytest -q
........................................                                                                                            [100%]
40 passed in 1.65s
PS C:\Users\melih\Development\8020 Fetcher> uv run mypy src
src\eticu\fit_parse.py:19: error: Skipping analyzing "fitdecode": module is installed, but missing library stubs or py.typed marker  [import-untyped]
src\eticu\fit_parse.py:19: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
src\eticu\intervals_client.py:49: error: Unused "type: ignore" comment  [unused-ignore]
src\eticu\intervals_client.py:50: error: Returning Any from function declared to return "list[dict[str, Any]]"  [no-any-return]
src\eticu\intervals_client.py:77: error: Unused "type: ignore" comment  [unused-ignore]
src\eticu\intervals_client.py:77: error: Returning Any from function declared to return "list[dict[str, Any]]"  [no-any-return]
src\eticu\intervals_client.py:77: note: Error code "no-any-return" not covered by "type: ignore[return-value]" comment
Found 5 errors in 2 files (checked 11 source files)

# Loop issue [RESOLVED]

- 8020/Z1 1s Z1
- 8020/Z2 1s Z2
2x
- 8020/Z3 1s Z4
- 8020/Z1 0s Z1

- 8020/Z2 1s Z2
- 8020/Z1 2s Z1

This is from intervals.icu

It is wrong, there should be a empty space before 2x so that loop is introduced correctly.

# Duration issue [RESOLVED]

for example in RF3:

- 8020/Z1 0s Z1 HR
- 8020/Z2 1s Z2 HR
- 8020/Z1 0s Z1 HR

(Fixed: FIT decode scaling for duration_value was incorrectly assumed to always be milliseconds. Duration parsing is now extracted as raw floating-point values since fitdecode automatically applies profile multipliers (producing seconds and meters directly).)

# Swim issue [RESOLVED]

INFO HTTP Request: GET https://intervals.icu/api/v1/athlete/i632678/folders "HTTP/1.1 200 OK"
INFO HTTP Request: POST https://intervals.icu/api/v1/athlete/i632678/workouts "HTTP/1.1 200 OK"
INFO Created workout 'SSI2 50m' (id=1064)
WARNING Step 4: no zone found in notes None — defaulting to Z1
WARNING Step has no zone; defaulting to 8020/Z1 (Z1)
WARNING Step has no zone; defaulting to 8020/Z1 (Z1)
WARNING Step has no zone; defaulting to 8020/Z1 (Z1)

(Fixed: convert.py no longer logs a warning for unzoned steps if their intensity is 'rest' or 'recovery', as these steps correctly don't require zones.)

# Too much workouts [RESOLVED]

INFO HTTP Request: POST https://intervals.icu/api/v1/athlete/i632678/workouts "HTTP/1.1 200 OK"
INFO Created workout 'STT2 50m' (id=1100)
  created=1100  updated=0  skipped=0  error=0

while scrape says

Total: 550  (Run=190  Ride=218  Swim=142)

So everythin is posted twice

# Intervals ICU Syntax Guide [RESOLVED]

Use https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701 for syntax. Reevaluate existing base with that guide.

(Evaluated and confirmed that the loops correctly use the empty line spacing syntax outlined in the guide, avoiding nested loop issues and correctly formatting `x` repeat blocks.)

