"""Check every link and image on the built page.

Internal links (#anchors, chart files) must resolve inside _site/. External
links are requested over the network and reported with their final status.
Some sites refuse scripted requests (a 403 or 999, or a 200 that is really a
"checking your browser" page, as LinkedIn serves); those are listed as "blocked, check in a browser" rather than counted as broken,
because a script can't tell a bot block from a dead page.

    python build.py && python scripts/check_links.py          # exits 1 on a broken link
    python scripts/check_links.py --offline                   # internal links only
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
UA = "Mozilla/5.0 (X11; Linux x86_64) nisha1324-portfolio-linkcheck"
BOT_BLOCK = {401, 403, 429, 999, "challenge page"}
# A 200 can still be a bot check rather than the page (LinkedIn does this).
CHALLENGE = ("checking your browser", "recaptcha", "just a moment...")


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.urls.append(a["href"])
        if tag in ("img", "link") and (a.get("src") or a.get("href")):
            self.urls.append(a.get("src") or a.get("href"))
        if tag == "meta" and a.get("property", "").startswith("og:") and \
                (a.get("content") or "").startswith("https://"):
            self.urls.append(a["content"])


def check_internal(url: str, ids: set[str], site: Path) -> str | None:
    """None if fine, else the reason it's broken."""
    if url.startswith("#"):
        return None if url[1:] in ids else "no element with this id"
    if url.startswith("mailto:"):
        return None if "@" in url else "bad address"
    return None if (site / url).is_file() else "file missing from _site/"


def fetch(url: str) -> tuple[str, int | str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            head = r.read(65536).decode("utf-8", "replace").lower()
            if any(s in head for s in CHALLENGE):
                return url, "challenge page"
            return url, r.status
    except urllib.error.HTTPError as exc:
        return url, exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return url, f"error: {getattr(exc, 'reason', exc)}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", type=Path, default=SITE)
    ap.add_argument("--offline", action="store_true", help="skip external links")
    args = ap.parse_args()

    page = Links()
    page.feed((args.site / "index.html").read_text())
    urls = list(dict.fromkeys(page.urls))  # unique, page order
    external = [u for u in urls if u.startswith(("http://", "https://"))]
    internal = [u for u in urls if u not in external]

    broken = []
    for u in internal:
        if (why := check_internal(u, page.ids, args.site)):
            broken.append((u, why))
    print(f"internal: {len(internal)} links, {len(broken)} broken")

    blocked = []
    if not args.offline:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch, external))
        for url, status in results:
            if status == 200:
                continue
            if status in BOT_BLOCK:
                blocked.append((url, status))
            else:
                broken.append((url, status))
        print(f"external: {len(external)} links, "
              f"{len(external) - len(blocked) - sum(u in external for u, _ in broken)} OK, "
              f"{len(blocked)} blocked")

    for url, status in blocked:
        print(f"  blocked ({status}), check in a browser: {url}")
    for url, why in broken:
        print(f"  BROKEN ({why}): {url}")
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
