"""Download .FIT files to a local cache directory.

Features:
- Resumable: skips files that already exist and are non-empty.
- Atomic writes: download to a .part file, then rename.
- Modest concurrency with a configurable thread count.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def local_path(url: str, cache_dir: Path) -> Path:
    """Map a .FIT URL to a local path, preserving the sport subfolder."""
    parts = [unquote(p) for p in urlparse(url).path.split("/") if p]
    tail = parts[-2:] if len(parts) >= 2 else parts[-1:]
    return cache_dir.joinpath(*tail)


def _download_one(
    client: httpx.Client,
    url: str,
    cache_dir: Path,
    retries: int = 3,
) -> tuple[str, str]:
    """Download a single file; return (url, status) where status ∈ ok/skip/error:…"""
    dest = local_path(url, cache_dir)
    if dest.exists() and dest.stat().st_size > 0:
        return url, "skip"

    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            with client.stream("GET", url, timeout=60) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
                tmp.replace(dest)
            return url, "ok"
        except httpx.HTTPError as exc:
            if attempt == retries:
                return url, f"error: {exc}"
            time.sleep(2 * attempt)
    return url, "error: exhausted retries"


def download_all(
    urls: list[str],
    cache_dir: Path,
    *,
    workers: int = 4,
    dry_run: bool = False,
) -> dict[str, int]:
    """Download a list of .FIT URLs into cache_dir.

    Returns counts: {"ok": N, "skip": N, "error": N}.
    """
    counts = {"ok": 0, "skip": 0, "error": 0}
    if not urls:
        return counts

    cache_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        for url in urls:
            dest = local_path(url, cache_dir)
            status = "skip" if (dest.exists() and dest.stat().st_size > 0) else "would-download"
            logger.info("[DRY-RUN] %s  %s", status, dest)

        def _needs_download(u: str) -> bool:
            p = local_path(u, cache_dir)
            return not (p.exists() and p.stat().st_size > 0)

        counts["ok"] = sum(1 for u in urls if _needs_download(u))
        counts["skip"] = len(urls) - counts["ok"]
        return counts

    with (
        httpx.Client(headers=_HEADERS, follow_redirects=True) as client,
        ThreadPoolExecutor(max_workers=workers) as pool,
    ):
        futures = {pool.submit(_download_one, client, u, cache_dir): u for u in urls}
        for i, fut in enumerate(as_completed(futures), 1):
            url, status = fut.result()
            dest = local_path(url, cache_dir)
            rel = dest.relative_to(cache_dir) if dest.is_relative_to(cache_dir) else dest
            if status == "ok":
                counts["ok"] += 1
                logger.info("[%4d/%d] OK   %s", i, len(urls), rel)
            elif status == "skip":
                counts["skip"] += 1
                logger.debug("[%4d/%d] SKIP %s", i, len(urls), rel)
            else:
                counts["error"] += 1
                logger.error("[%4d/%d] FAIL %s  (%s)", i, len(urls), rel, status)

    return counts
