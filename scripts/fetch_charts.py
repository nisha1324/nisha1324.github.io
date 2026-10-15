"""Download each project's key chart from its repo at the pinned commit.

The chart files are committed under assets/charts/ so the site builds offline.
This script is how they got there, and re-running it must give identical bytes
(the commit is pinned). assets/charts/SOURCES.json records where each file came
from and its SHA-256, which build.py checks.

    python scripts/fetch_charts.py            # download any missing charts
    python scripts/fetch_charts.py --force    # re-download all of them
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHART_DIR = ROOT / "assets" / "charts"
SOURCES = CHART_DIR / "SOURCES.json"
OWNER = "nisha1324"
RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{path}"


def chart_url(project: dict) -> str:
    return RAW.format(owner=OWNER, repo=project["slug"],
                      commit=project["chart_commit"], path=project["chart"])


def download(url: str, attempts: int = 3) -> bytes:
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or i == attempts - 1:
                raise  # a 404 means a wrong commit or path: don't retry
            print(f"  retry after error: {exc}", file=sys.stderr)
            time.sleep(2 ** i)
        except OSError as exc:  # URLError and timeouts
            if i == attempts - 1:
                raise
            print(f"  retry after error: {exc}", file=sys.stderr)
            time.sleep(2 ** i)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="re-download existing charts")
    args = ap.parse_args()

    projects = tomllib.loads((ROOT / "projects.toml").read_text())["project"]
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    sources = {}
    for p in projects:
        dest = CHART_DIR / f"{p['slug']}.png"
        url = chart_url(p)
        if args.force or not dest.exists():
            body = download(url)
            if not body.startswith(b"\x89PNG\r\n\x1a\n"):
                sys.exit(f"{url} did not return a PNG")
            dest.write_bytes(body)
            print(f"fetched {dest.name} ({len(body):,} bytes)")
        sources[dest.name] = {
            "url": url,
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        }
    SOURCES.write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n")
    print(f"wrote {SOURCES.relative_to(ROOT)} ({len(sources)} charts)")


if __name__ == "__main__":
    main()
