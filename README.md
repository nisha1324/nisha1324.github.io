# nisha1324.github.io

Source for my portfolio site, **https://nisha1324.github.io**: one page that shows each of my data projects as a business question, a headline number, what it means for the business, and the project's key chart.

> **Status:** complete and live at https://nisha1324.github.io. New projects are added as they finish.

## Why a build script and not a hand-written page?
A portfolio is only useful if every number on it is true. The page is generated from one file, [`projects.toml`](projects.toml), and the build refuses to publish when something doesn't add up:

- **Figures come from the projects themselves.** Every number in `projects.toml` is copied from that project's README (its TL;DR or findings), which in turn comes from the code's output. Nothing is rounded up or reworded into a bigger claim.
- **Charts are pinned.** Each chart is downloaded from its repo at a fixed commit, and its SHA-256 is recorded in [`assets/charts/SOURCES.json`](assets/charts/SOURCES.json). If a chart file changes, or `projects.toml` points at a different commit, the build stops.
- **Only live, public projects are shown.** Before each deploy, the workflow asks the GitHub REST API about every repo. A repo that is missing, private, archived or a fork stops the build, so the site can't link to something that isn't there.

## How it works

```
projects.toml ──┐
assets/charts/ ─┼─► build.py ─► _site/ (index.html, style.css, charts) ─► GitHub Pages
data/repos.json ┘        ▲
       ▲                 └─ templates/index.html, static/style.css
       └─ scripts/sync_github.py  (GitHub REST API: description, topics, last commit)
          scripts/fetch_charts.py (raw.githubusercontent.com at the pinned commit)
```

| Piece | What it does |
|---|---|
| [`projects.toml`](projects.toml) | The content: question, headline stat, finding, "so what", tools, dataset and chart for each project |
| [`build.py`](build.py) | Validates the inputs and renders the page with the standard library only (`tomllib`, `html.escape`, `string.Template`). Every value is HTML-escaped, and image sizes are read from the PNG header so the page doesn't jump while charts load |
| [`scripts/fetch_charts.py`](scripts/fetch_charts.py) | Downloads each chart at its pinned commit and records its source URL and hash |
| [`scripts/sync_github.py`](scripts/sync_github.py) | Pulls repo metadata from the GitHub API (no key needed; uses `GITHUB_TOKEN` in Actions) |
| [`scripts/check_links.py`](scripts/check_links.py) | Checks every link and image on the built page: anchors and files offline, external links over the network. Sites that show scripts a bot check are listed separately to check in a browser |
| [`scripts/make_og_image.py`](scripts/make_og_image.py) | Renders the 1200×630 link-preview image ([`static/og.png`](static/og.png)) from `projects.toml` with headless Chrome, so the picture shown when the URL is shared always matches the page |
| [`.github/workflows/pages.yml`](.github/workflows/pages.yml) | On every push and every Monday: run the tests, refresh the metadata, build, check internal links, and deploy to GitHub Pages |

The page works on phones, follows the system light/dark setting, has alt text for every chart, and its text and button colours pass WCAG AA contrast. It also works from the keyboard alone: a "skip to projects" link comes first, the tab order follows the page, and every link shows a visible focus outline (checked by tabbing through the page in headless Chrome). When the URL is shared, Open Graph tags give a title, description and preview image.

### Link check (2026-10-15)
`scripts/check_links.py` on the built page: all 19 internal links and images resolve, and 18 of 21 external links (including the live preview image) return 200 directly. LinkedIn, NYC Open Data and Kaggle show scripts a "checking your browser" page instead. NYC Open Data and Kaggle opened normally in headless Chrome. LinkedIn asks logged-out visitors to sign in, so no script can confirm that link; it's the same URL as on my GitHub profile.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements.txt                     # pytest only; the build is stdlib
python build.py                                     # → _site/index.html
python -m http.server -d _site 8000                 # view at http://localhost:8000
python -m pytest -q                                 # 13 offline tests
python scripts/check_links.py                       # all links (add --offline for internal only)
```

Optional refreshes (need network): `python scripts/sync_github.py` and `python scripts/fetch_charts.py --force`. After changing the name, headline or project list, run `python scripts/make_og_image.py` (needs Chrome) to redraw the preview image.

### Adding a project
1. Add a `[[project]]` block to `projects.toml`, copying figures from the project's README.
2. Run `python scripts/fetch_charts.py` to download its chart at the pinned commit.
3. Run `python scripts/make_og_image.py`, `python scripts/sync_github.py`, `python build.py`, the tests and `python scripts/check_links.py`, then look at the page.

## Tests
`tests/test_build.py` builds the site from the real inputs and checks that every project has a card, an anchor, a repo link and a chart with alt text and size, with no duplicate ids. Other tests check the Open Graph tags and the 1200×630 preview image, check that every internal link and image resolves, and check that two builds give identical bytes, and that the build fails on broken inputs: a missing field, a tampered chart, a chart re-pinned without re-fetching, and a private, archived or forked repo. One test makes sure text is HTML-escaped.

## Data credits
The charts are outputs of the linked projects, which use: NYC Open Data 311 Service Requests (NYC.gov Terms of Use); HM Land Registry Price Paid Data (© Crown copyright, OGL v3.0); UCI Sentiment Labelled Sentences, UCI Online Retail and UCI Online Retail II (CC BY 4.0); Olist Brazilian E-commerce (© Olist, CC BY-NC-SA 4.0); ECB reference rates via the Frankfurter API; Homes Victoria Rental Report – Quarterly, and ABS Consumer Price Index, Building Approvals and Census 2021 data (CC BY 4.0); BITRE Domestic Airlines – On Time Performance (CC BY 3.0 AU); and the Chinook sample database. Each project's README has the full citation.
