#!/usr/bin/env python3
"""Download test fixture files from the 80/20 Endurance public library.

Run once to populate tests/fixtures/ then commit the .FIT files.

    uv run python tests/download_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

_FIXTURE_DIR = Path(__file__).parent / "fixtures"

_FIXTURES = {
    "CCI1.FIT": "https://www.8020endurance.com/wp-content/library/bike/CCI1.FIT",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def main() -> int:
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    ok = err = 0
    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        for name, url in _FIXTURES.items():
            dest = _FIXTURE_DIR / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"SKIP  {name}")
                ok += 1
                continue
            print(f"GET   {url}")
            try:
                r = client.get(url)
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(r.content)
                tmp.replace(dest)
                print(f"OK    {name} ({dest.stat().st_size} bytes)")
                ok += 1
            except Exception as exc:
                print(f"FAIL  {name}: {exc}", file=sys.stderr)
                err += 1
    print(f"\nDone: ok={ok} err={err}")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
