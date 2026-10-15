"""Offline tests for the site build: real inputs, plus broken copies of them."""
from __future__ import annotations

import json
import re
import shutil
import tomllib
from html.parser import HTMLParser
from pathlib import Path

import pytest

import build

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A copy of the build inputs that a test can break without touching the repo."""
    for name in ("projects.toml", "templates", "static", "assets", "data"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, tmp_path / name)
        else:
            shutil.copy2(src, tmp_path / name)
    return tmp_path


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.imgs: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "a":
            self.hrefs.append(a.get("href", ""))
        if tag == "img":
            self.imgs.append(a)


def parse(html: str) -> Collector:
    c = Collector()
    c.feed(html)
    return c


def test_real_inputs_build(workspace):
    out = build.build(workspace, workspace / "_site")
    html = (out / "index.html").read_text()
    projects = tomllib.loads((workspace / "projects.toml").read_text())["project"]
    page = parse(html)

    assert len(page.imgs) == len(projects)
    for img in page.imgs:
        assert img["alt"].strip(), "every chart needs alt text"
        assert (out / img["src"]).exists()
        assert int(img["width"]) > 0 and int(img["height"]) > 0
    for p in projects:
        assert p["slug"] in page.ids
        assert f"#{p['slug']}" in page.hrefs
        assert f"https://github.com/nisha1324/{p['slug']}" in page.hrefs
    assert len(page.ids) == len(set(page.ids)), "duplicate ids"
    assert (out / ".nojekyll").exists()


def test_link_preview_tags(workspace):
    out = build.build(workspace, workspace / "_site")
    html = (out / "index.html").read_text()
    url = tomllib.loads((workspace / "projects.toml").read_text())["site"]["url"]
    assert url.endswith("/")
    assert f'<meta property="og:image" content="{url}og.png">' in html
    assert f'<link rel="canonical" href="{url}">' in html
    assert build.png_size(out / "og.png") == (1200, 630)


def test_wrong_size_preview_fails(workspace):
    shutil.copy2(workspace / "assets" / "charts" / "ecommerce-funnel-duckdb.png",
                 workspace / "static" / "og.png")
    with pytest.raises(build.BuildError, match="1200x630"):
        build.build(workspace, workspace / "_site")


def test_internal_links_resolve(workspace):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_links

    out = build.build(workspace, workspace / "_site")
    page = check_links.Links()
    page.feed((out / "index.html").read_text())
    internal = [u for u in page.urls if not u.startswith(("http://", "https://"))]
    assert internal, "expected anchors and chart links"
    assert [u for u in internal if check_links.check_internal(u, page.ids, out)] == []
    assert check_links.check_internal("#nope", page.ids, out)  # and it does catch breaks


def test_build_is_deterministic(workspace):
    first = (build.build(workspace, workspace / "a") / "index.html").read_bytes()
    second = (build.build(workspace, workspace / "b") / "index.html").read_bytes()
    assert first == second


def test_text_is_escaped(workspace):
    toml = workspace / "projects.toml"
    toml.write_text(toml.read_text().replace(
        'title = "SQL Business Analytics"', 'title = "SQL <script>alert(1)</script> & Co"', 1))
    html = (build.build(workspace, workspace / "_site") / "index.html").read_text()
    assert "<script>" not in html
    assert "SQL &lt;script&gt;alert(1)&lt;/script&gt; &amp; Co" in html


def test_missing_field_fails(workspace):
    toml = workspace / "projects.toml"
    toml.write_text(re.sub(r'(?m)^so_what = .*\n', "", toml.read_text(), count=1))
    with pytest.raises(build.BuildError, match="missing 'so_what'"):
        build.build(workspace, workspace / "_site")


def test_tampered_chart_fails(workspace):
    chart = next((workspace / "assets" / "charts").glob("*.png"))
    chart.write_bytes(chart.read_bytes() + b"x")
    with pytest.raises(build.BuildError, match="differs from the file recorded"):
        build.build(workspace, workspace / "_site")


def test_repinned_chart_needs_refetch(workspace):
    toml = workspace / "projects.toml"
    toml.write_text(toml.read_text().replace(
        "673c03e4959b07fe264bacb866c4c0542ff47521", "0" * 40))
    with pytest.raises(build.BuildError, match="doesn't match projects.toml"):
        build.build(workspace, workspace / "_site")


@pytest.mark.parametrize("flag", ["private", "archived", "fork"])
def test_unpublishable_repo_fails(workspace, flag):
    path = workspace / "data" / "repos.json"
    repos = json.loads(path.read_text())
    repos["fx-rates-pipeline"][flag] = True
    path.write_text(json.dumps(repos))
    with pytest.raises(build.BuildError, match=f"is {flag}"):
        build.build(workspace, workspace / "_site")


def test_png_size_reads_header():
    w, h = build.png_size(ROOT / "assets" / "charts" / "ecommerce-funnel-duckdb.png")
    assert (w, h) == (1200, 540)  # checked independently with Pillow
