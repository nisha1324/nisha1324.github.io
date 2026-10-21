"""Render the link-preview image (static/og.png, 1200×630) from projects.toml.

This is the picture LinkedIn, Slack, WhatsApp and others show when someone
shares the site's URL. It's generated rather than hand-drawn, so the name,
headline and project list always match the page. It uses headless Chrome to
render a small HTML card, so it needs Chrome installed; the PNG is committed and
the site build itself doesn't need Chrome.

    python scripts/make_og_image.py              # rewrites static/og.png
    python scripts/make_og_image.py --chrome /path/to/chrome
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import tomllib
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "og.png"
W, H = 1200, 630

CARD = """<!doctype html><html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; width: {w}px; height: {h}px; overflow: hidden; }}
body {{ background: #fcfcfb; color: #0b0b0b; box-sizing: border-box;
       font-family: system-ui, "DejaVu Sans", sans-serif; padding: 52px 72px 48px;
       border-top: 14px solid #1f5fae; display: flex; flex-direction: column; }}
h1 {{ font-size: 76px; margin: 0; line-height: 1.05; }}
.headline {{ font-size: 30px; color: #52514e; margin: 12px 0 30px; font-weight: 600; }}
.count {{ font-size: 24px; text-transform: uppercase; letter-spacing: .06em; color: #52514e; margin: 0 0 14px; }}
ul {{ list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 10px; }}
li {{ font-size: 24px; padding: 6px 16px; border-radius: 999px; background: #f2f1ed; }}
.url {{ margin: auto 0 0; padding-top: 22px; font-size: 28px; font-weight: 700; color: #1f5fae; }}
</style></head><body>
<h1>{name}</h1>
<p class="headline">{headline}</p>
<p class="count">{count} data projects · real public data · business findings</p>
<ul>{chips}</ul>
<p class="url">{url}</p>
</body></html>"""


def card_html(doc: dict) -> str:
    site, projects = doc["site"], doc["project"]
    return CARD.format(
        w=W, h=H,
        name=escape(site["name"]),
        headline=escape(site["og_headline"]),
        count=len(projects),
        chips="".join(f"<li>{escape(p['title'])}</li>" for p in projects),
        url=escape(site["url"].removeprefix("https://").rstrip("/")),
    )


def find_chrome(given: str | None) -> str:
    for name in ([given] if given else []) + ["google-chrome", "chromium", "chromium-browser"]:
        if path := shutil.which(name):
            return path
    sys.exit("Chrome/Chromium not found: pass --chrome /path/to/chrome")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    doc = tomllib.loads((ROOT / "projects.toml").read_text())
    chrome = find_chrome(args.chrome)
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "og.html"
        page.write_text(card_html(doc))
        shot = Path(tmp) / "og.png"
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={W},{H}", f"--screenshot={shot}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
        args.out.write_bytes(shot.read_bytes())
    print(f"wrote {args.out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
