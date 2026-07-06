"""Discover .FIT workout URLs from the 80/20 Endurance public workout library.

Groups URLs by sport based on the URL path segment (run/bike/swim).
Swim URLs are pre-filtered to 25m and 50m only (never 25y).
"""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import unquote, urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_LIBRARY_URL = "https://www.8020endurance.com/8020-workout-library/"
_FIT_HREF = re.compile(r'href\s*=\s*["\']([^"\']+?\.fit)["\']', re.IGNORECASE)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Swim filename patterns to include/exclude
_SWIM_KEEP = re.compile(r"\b(25m|50m)\b", re.IGNORECASE)
_SWIM_SKIP = re.compile(r"\b25y\b", re.IGNORECASE)


def _sport_from_url(url: str) -> str:
    """Infer sport from URL path segment (run/bike/swim)."""
    path = urlparse(url).path.lower()
    if "/run/" in path:
        return "Run"
    if "/bike/" in path:
        return "Ride"
    if "/swim/" in path:
        return "Swim"
    return "Run"


def _keep_swim(url: str) -> bool:
    """Return True if this swim URL should be kept (25m or 50m, not 25y)."""
    # URL-decode so "SCI1%2025m.FIT" → "SCI1 25m.FIT" before pattern matching.
    filename = unquote(urlparse(url).path.split("/")[-1])
    if _SWIM_SKIP.search(filename):
        return False
    return bool(_SWIM_KEEP.search(filename))


def scrape_workout_urls(
    *,
    delay: float = 0.5,
    timeout: float = 30.0,
) -> dict[str, list[str]]:
    """Return a dict mapping sport → list of .FIT URLs.

    Swim entries are pre-filtered: 25m and 50m kept, 25y skipped.
    """
    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=timeout) as client:
        logger.info("Fetching library index from %s", _LIBRARY_URL)
        resp = client.get(_LIBRARY_URL)
        resp.raise_for_status()
        time.sleep(delay)

    all_urls = sorted({urljoin(_LIBRARY_URL, m) for m in _FIT_HREF.findall(resp.text)})
    logger.info("Found %d .FIT URLs total", len(all_urls))

    grouped: dict[str, list[str]] = {"Run": [], "Ride": [], "Swim": []}
    skipped_swim = 0
    for url in all_urls:
        sport = _sport_from_url(url)
        if sport == "Swim" and not _keep_swim(url):
            skipped_swim += 1
            logger.debug("Skipping swim URL (not 25m/50m): %s", url)
            continue
        grouped[sport].append(url)

    total = sum(len(v) for v in grouped.values())
    logger.info(
        "Kept %d URLs — Run: %d  Ride: %d  Swim: %d  (skipped %d swim)",
        total,
        len(grouped["Run"]),
        len(grouped["Ride"]),
        len(grouped["Swim"]),
        skipped_swim,
    )
    return grouped
