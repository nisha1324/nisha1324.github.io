"""Refresh repo metadata for every project from the GitHub REST API.

Writes data/repos.json, which build.py uses for the "last commit" date and to
refuse to publish a card whose repo is missing, private or archived. The file is
committed so the site builds offline; the Pages workflow refreshes it before
every build.

No key is needed (the unauthenticated limit is 60 requests an hour, and this
makes one per project). If GITHUB_TOKEN is set, as it is in GitHub Actions, it
is sent to get the higher limit.

    python scripts/sync_github.py
"""
from __future__ import annotations

import json
import os
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "repos.json"
API = "https://api.github.com/repos/{owner}/{repo}"
OWNER = "nisha1324"
KEEP = ("name", "html_url", "description", "topics", "private", "archived",
        "fork", "pushed_at", "language")


def fetch_repo(repo: str, token: str | None) -> dict:
    req = urllib.request.Request(API.format(owner=OWNER, repo=repo), headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{OWNER}-portfolio-build",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"GitHub API {exc.code} for {OWNER}/{repo}: {exc.reason}")
    return {k: data.get(k) for k in KEEP}


def main() -> None:
    projects = tomllib.loads((ROOT / "projects.toml").read_text())["project"]
    token = os.environ.get("GITHUB_TOKEN") or None
    repos = {p["slug"]: fetch_repo(p["slug"], token) for p in projects}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(repos, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(repos)} repos)")


if __name__ == "__main__":
    main()
