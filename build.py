"""Build the static portfolio site into _site/.

Inputs (all committed, so the build is offline and deterministic):
  projects.toml            curated text for each project, figures copied from its README
  assets/charts/*.png      each project's key chart (scripts/fetch_charts.py)
  data/repos.json          repo metadata from the GitHub API (scripts/sync_github.py)
  templates/, static/      page template and stylesheet

The build stops with an error instead of publishing something wrong: a missing
field, a chart whose bytes don't match SOURCES.json, or a repo that is missing,
private, archived or a fork.

    python build.py            # writes _site/
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import tomllib
from datetime import date
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"

SITE_FIELDS = ("name", "headline", "intro", "github", "linkedin", "email")
PROJECT_FIELDS = ("slug", "title", "kind", "finished", "question", "stat", "stat_label",
                  "finding", "so_what", "stack", "data", "data_url", "chart",
                  "chart_commit", "chart_alt")


class BuildError(Exception):
    pass


def load_projects(path: Path) -> tuple[dict, list[dict]]:
    doc = tomllib.loads(path.read_text())
    site, projects = doc.get("site", {}), doc.get("project", [])
    for f in SITE_FIELDS:
        if not site.get(f):
            raise BuildError(f"[site] is missing '{f}'")
    if not projects:
        raise BuildError("projects.toml has no [[project]] entries")
    seen = set()
    for p in projects:
        name = p.get("slug", "?")
        for f in PROJECT_FIELDS:
            if not p.get(f):
                raise BuildError(f"project '{name}' is missing '{f}'")
        if name in seen:
            raise BuildError(f"duplicate slug '{name}'")
        seen.add(name)
        date.fromisoformat(p["finished"])  # raises ValueError on a bad date
        if len(p["chart_commit"]) != 40:
            raise BuildError(f"project '{name}': chart_commit must be a full 40-char SHA")
    return site, projects


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the PNG header, so <img> can reserve its space."""
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise BuildError(f"{path.name} is not a PNG")
    return struct.unpack(">II", head[16:24])


def check_charts(projects: list[dict], chart_dir: Path) -> None:
    sources = json.loads((chart_dir / "SOURCES.json").read_text())
    for p in projects:
        name = f"{p['slug']}.png"
        f = chart_dir / name
        if not f.exists():
            raise BuildError(f"missing chart {name}: run scripts/fetch_charts.py")
        src = sources.get(name)
        if src is None or p["chart_commit"] not in src["url"] or not src["url"].endswith(p["chart"]):
            raise BuildError(f"{name} doesn't match projects.toml: run scripts/fetch_charts.py --force")
        if hashlib.sha256(f.read_bytes()).hexdigest() != src["sha256"]:
            raise BuildError(f"{name} differs from the file recorded in SOURCES.json")


def check_repos(projects: list[dict], repos: dict) -> None:
    for p in projects:
        meta = repos.get(p["slug"])
        if meta is None:
            raise BuildError(f"no GitHub metadata for '{p['slug']}': run scripts/sync_github.py")
        for flag in ("private", "archived", "fork"):
            if meta.get(flag):
                raise BuildError(f"repo '{p['slug']}' is {flag}; it shouldn't be on the site")


def e(text: str) -> str:
    return escape(str(text), quote=True)


def render_card(p: dict, meta: dict, chart_dir: Path) -> str:
    w, h = png_size(chart_dir / f"{p['slug']}.png")
    repo = meta["html_url"]
    tags = "".join(f"<li>{e(s)}</li>" for s in p["stack"])
    updated = meta["pushed_at"][:10]
    return f"""
<article class="card" id="{e(p['slug'])}" aria-labelledby="{e(p['slug'])}-title">
  <div class="card-text">
    <p class="kind">{e(p['kind'])}</p>
    <h2 id="{e(p['slug'])}-title"><a href="{e(repo)}">{e(p['title'])}</a></h2>
    <p class="question">{e(p['question'])}</p>
    <div class="stat"><span class="stat-value">{e(p['stat'])}</span>
      <span class="stat-label">{e(p['stat_label'])}</span></div>
    <p>{e(p['finding'])}</p>
    <p class="so-what"><strong>So what:</strong> {e(p['so_what'])}</p>
    <ul class="stack" aria-label="Tools">{tags}</ul>
    <p class="meta">Data: <a href="{e(p['data_url'])}">{e(p['data'])}</a>
      · <span class="nowrap">Finished {e(p['finished'])}</span>
      · <span class="nowrap">Last commit {e(updated)}</span></p>
    <p class="links"><a class="button" href="{e(repo)}">Code &amp; full write-up</a></p>
  </div>
  <figure class="card-chart">
    <a href="assets/charts/{e(p['slug'])}.png"><img src="assets/charts/{e(p['slug'])}.png"
      width="{w}" height="{h}" loading="lazy" alt="{e(p['chart_alt'])}"></a>
  </figure>
</article>"""


def render_page(site: dict, projects: list[dict], repos: dict, chart_dir: Path,
                template: str) -> str:
    nav = "".join(f'<li><a href="#{e(p["slug"])}">{e(p["title"])}</a></li>' for p in projects)
    cards = "".join(render_card(p, repos[p["slug"]], chart_dir) for p in projects)
    return Template(template).substitute(
        name=e(site["name"]),
        headline=e(site["headline"]),
        intro=e(site["intro"]),
        github=e(site["github"]),
        linkedin=e(site["linkedin"]),
        email=e(site["email"]),
        count=len(projects),
        nav=nav,
        cards=cards,
    )


def build(root: Path = ROOT, out: Path = OUT) -> Path:
    site, projects = load_projects(root / "projects.toml")
    chart_dir = root / "assets" / "charts"
    repos = json.loads((root / "data" / "repos.json").read_text())
    check_charts(projects, chart_dir)
    check_repos(projects, repos)
    html = render_page(site, projects, repos, chart_dir,
                       (root / "templates" / "index.html").read_text())

    if out.exists():
        shutil.rmtree(out)
    (out / "assets" / "charts").mkdir(parents=True)
    (out / "index.html").write_text(html)
    shutil.copy2(root / "static" / "style.css", out / "style.css")
    for p in projects:
        shutil.copy2(chart_dir / f"{p['slug']}.png", out / "assets" / "charts")
    (out / ".nojekyll").write_text("")  # serve files as-is, no Jekyll pass
    return out


def main() -> None:
    try:
        out = build()
    except (BuildError, ValueError) as exc:
        sys.exit(f"build failed: {exc}")
    files = sorted(p for p in out.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in files)
    print(f"built {out.relative_to(ROOT)}/ ({len(files)} files, {size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
