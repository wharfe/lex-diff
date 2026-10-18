"""Check the built /upcoming page against the shipped pending diffs.

Usage:
    python scripts/check_upcoming_page.py <out_dir> [--data-dir DIR] [--today YYYY-MM-DD]

--today replaces the page file's modification date (JST) as the day its
recorded build date is judged against.

The page is static and the frontend has no test runner, so this reads the
exported HTML and compares it with frontend/public/data/ (docs/upcoming-page/spec.md).
It reads the visible text, not only the markers: a section is
<section data-upcoming-section="YYYY-MM|unfixed"> whose first <h2> is its
heading, and a row is the <a href="/diff/{id}" data-pending-id> inside it,
holding all of the row's text. The wording below is the page's, copied from
frontend/lib/pending.ts on purpose: a change there has to be made here too.
Exit 1 on any mismatch. Run by hand after a build (CI does not run it).
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SHIPPED = Path(__file__).parent.parent / "frontend" / "public" / "data"
BASE = "https://lexdiff.com"

TITLE = "施行予定の法改正一覧 | lexdiff"
# Dated by each row's record, not asserted of the reader's present: a search
# snippet outlives the date it describes (codex, Gate3).
DESCRIPTION = "e-Gov の記録で未施行だった法改正の一覧です（記録の日付は各行に表示）。施行されると変わる条文を新旧の差分で確認できます。"
INTRO = (
    "成立済みで、各行の日付の時点では未施行だった改正です。"
    "施行されると変わる条文を差分で確認できます（AIによる解説はありません）"
)
SCOPE = (
    "lexdiff が収録する法令のうち、差分を作れた改正のみを載せています"
    "（e-Gov に施行日の記載がない改正や、条文中の表が変わる改正は載せていません）"
)
UNFIXED_HEADING = "各行の日付の時点で、施行日が e-Gov 上で確定していなかった改正"
EMPTY = "掲載できる施行予定の改正はありません"


def month_heading(month: str) -> str:
    y, m = month.split("-")
    return f"施行日が{int(y)}年{int(m)}月の改正"


def row_texts(doc: dict) -> list[str]:
    """A row's strings in the order the page shows them, as lib/pending.ts
    builds them. The row's text must be exactly their concatenation, so a
    contradicting extra string fails too (code-review, Gate3)."""
    p = doc["pending"]
    name = "／".join(
        r.get("amendment_law_num") or r.get("amendment_law_title") or r["law_revision_id"]
        for r in p["revisions"]
    )
    labels = "／".join(
        f"{r['enforcement_comment']}（e-Gov 上の予定日: {doc['date_after']}）"
        if r.get("enforcement_comment") else doc["date_after"]
        for r in p["revisions"]
    )
    # Counted from the diffs, as the page's mainChangeCounts does — not from
    # the published stats, which the page does not read.
    main = sum(1 for d in doc["diffs"] if not d.get("is_suppl"))
    stats = f"施行されると本則 {main} 条が変わる" if main > 0 else "本則は変わらない"
    texts = [doc["law_title"], name, f"{p['generated_on']}時点で未施行",
             f"施行日: {labels}", stats]
    if p.get("unenforced_before"):
        texts.append(
            f"（{p['generated_on']}時点で未施行の他の改正 {len(p['unenforced_before'])} 件を反映した条文との比較）"
        )
    return texts


def expected_rows(data_dir: Path, build_date: str) -> dict[str, dict]:
    rows = {}
    for path in data_dir.glob("*_*_*.json"):
        doc = json.loads(path.read_text())
        if "pending" not in doc or doc["date_after"] <= build_date:
            continue
        unfixed = any(r.get("enforcement_comment") for r in doc["pending"]["revisions"])
        rows[path.stem] = {
            "date": doc["date_after"],
            "where": "unfixed" if unfixed else doc["date_after"][:7],
            "generated_on": doc["pending"]["generated_on"],
            "texts": row_texts(doc),
        }
    return rows


class PageReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth_main = 0
        self.mains = 0
        self.main_diff_links: list[str] = []
        self.section: dict | None = None
        self.sections: list[dict] = []
        self.row: dict | None = None
        self.h2: list[str] | None = None
        self.title: list[str] | None = None
        self.title_text = ""
        self.meta: dict[str, str] = {}
        self.canonical = None
        self.build_dates: list[str] = []
        self.main_text: list[str] = []
        self.home_section_links: list[str] = []
        self.in_home_section = 0
        # One entry per open <section>, so a nested one closes only itself.
        self.section_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "main":
            self.mains += 1
            self.depth_main += 1
        if tag == "title":
            self.title = []
        if tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key] = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        if "data-build-date" in a:
            self.build_dates.append(a["data-build-date"])
        if tag == "section":
            if "data-home-upcoming" in a:
                self.in_home_section += 1
                self.section_stack.append("home")
            elif "data-upcoming-section" in a:
                self.section = {"key": a["data-upcoming-section"], "heading": None, "rows": []}
                self.sections.append(self.section)
                self.section_stack.append("upcoming")
            else:
                self.section_stack.append("other")
        if tag == "h2" and self.section is not None and self.section["heading"] is None:
            self.h2 = []
        if tag == "a":
            href = a.get("href") or ""
            if self.depth_main and href.startswith("/diff/"):
                self.main_diff_links.append(href)
            if self.in_home_section:
                self.home_section_links.append(href)
            if "data-pending-id" in a:
                self.row = {"id": a["data-pending-id"], "href": href, "text": []}
                if self.section is not None:
                    self.section["rows"].append(self.row)
                else:
                    self.sections.append({"key": None, "heading": None, "rows": [self.row]})

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.depth_main -= 1
        if tag == "title" and self.title is not None:
            self.title_text = "".join(self.title)
            self.title = None
        if tag == "h2" and self.h2 is not None:
            self.section["heading"] = "".join(self.h2)
            self.h2 = None
        if tag == "a" and self.row is not None:
            self.row["text"] = "".join(self.row["text"])
            self.row = None
        if tag == "section" and self.section_stack:
            kind = self.section_stack.pop()
            if kind == "upcoming":
                self.section = None
            elif kind == "home":
                self.in_home_section -= 1

    def handle_data(self, data: str) -> None:
        if self.title is not None:
            self.title.append(data)
        if self.h2 is not None:
            self.h2.append(data)
        if self.row is not None:
            self.row["text"].append(data)
        if self.depth_main:
            self.main_text.append(data)


def check_sitemap(path: Path) -> list[str]:
    """/upcoming is listed, with no lastmod in its <url> wherever it sits."""
    if not path.exists():
        return ["sitemap.xml does not exist"]
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = [u for u in ET.parse(path).getroot().iter(f"{ns}url")
            if u.findtext(f"{ns}loc") == f"{BASE}/upcoming"]
    if len(urls) != 1:
        return [f"sitemap.xml lists /upcoming {len(urls)} times"]
    if urls[0].find(f"{ns}lastmod") is not None:
        return ["sitemap gives /upcoming a lastmod"]
    return []


def check(out_dir: Path, data_dir: Path, today: str | None) -> list[str]:
    """`today` defaults to the page file's own date in JST: the build date it
    records must be that day or the one before (a build crossing midnight)."""
    page = out_dir / "upcoming.html"
    if not page.exists():
        return [f"{page} does not exist"]
    r = PageReader()
    r.feed(page.read_text())
    errors: list[str] = []

    # The page's own build date, checked before it is trusted (Gate2 r2 M4).
    if len(r.build_dates) != 1:
        return [f"expected one data-build-date, found {r.build_dates}"]
    build_date = r.build_dates[0]
    if today is None:
        today = datetime.fromtimestamp(page.stat().st_mtime, JST).date().isoformat()
    day_before = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    if build_date not in (today, day_before):
        errors.append(f"data-build-date {build_date} is neither {today} nor the day before")
    expected = expected_rows(data_dir, build_date)
    if expected and build_date < max(x["generated_on"] for x in expected.values()):
        errors.append(f"data-build-date {build_date} precedes a generated_on")

    if r.mains != 1:
        errors.append(f"{r.mains} <main> elements")
    if r.title_text != TITLE:
        errors.append(f"title {r.title_text!r}")
    for key, want in [("description", DESCRIPTION), ("og:title", TITLE),
                      ("og:description", DESCRIPTION), ("og:url", f"{BASE}/upcoming"),
                      ("og:site_name", "lexdiff"), ("og:locale", "ja_JP"),
                      ("og:type", "website")]:
        if r.meta.get(key) != want:
            errors.append(f"meta {key} = {r.meta.get(key)!r}")
    if r.canonical != f"{BASE}/upcoming":
        errors.append(f"canonical {r.canonical!r}")

    text = "".join(r.main_text)
    for want in (INTRO, SCOPE):
        if want not in text:
            errors.append(f"missing text: {want[:20]}…")

    # Every /diff/ link in <main> is a row, and the set is exactly the expected one.
    targets = [h.removeprefix("/diff/") for h in r.main_diff_links]
    if sorted(targets) != sorted(expected):
        missing = sorted(set(expected) - set(targets))
        extra = sorted(set(targets) - set(expected))
        dup = sorted({t for t in targets if targets.count(t) > 1})
        errors.append(f"/diff/ links: missing {missing} extra {extra} repeated {dup}")

    # Rows, not only links: a row stripped of its marker would skip every
    # text check below while the link set still agreed (codex, Gate3).
    row_ids = [row["id"] for s in r.sections for row in s["rows"]]
    if sorted(row_ids) != sorted(expected):
        errors.append(f"rows {sorted(row_ids)} != expected {sorted(expected)}")

    keys = [s["key"] for s in r.sections]
    want_months = sorted({x["where"] for x in expected.values() if x["where"] != "unfixed"})
    want_keys = want_months + (["unfixed"] if any(x["where"] == "unfixed" for x in expected.values()) else [])
    if keys != want_keys:
        errors.append(f"sections {keys}, expected {want_keys}")
    for s in r.sections:
        want_heading = UNFIXED_HEADING if s["key"] == "unfixed" else (
            month_heading(s["key"]) if s["key"] else None)
        if s["heading"] != want_heading:
            errors.append(f"section {s['key']}: heading {s['heading']!r}")
        ids = [row["id"] for row in s["rows"]]
        want_order = sorted((i for i in ids if i in expected),
                            key=lambda i: (expected[i]["date"], i))
        if ids != want_order:
            errors.append(f"section {s['key']}: rows {ids} not in date→id order")
        for row in s["rows"]:
            x = expected.get(row["id"])
            if x is None:
                continue
            if row["href"] != f"/diff/{row['id']}":
                errors.append(f"{row['id']}: href {row['href']!r}")
            if s["key"] != x["where"]:
                errors.append(f"{row['id']}: in section {s['key']!r}, expected {x['where']!r}")
            want_text = "".join(x["texts"])
            if row["text"] != want_text:
                errors.append(f"{row['id']}: row text {row['text']!r} != {want_text!r}")

    if not expected and EMPTY not in text:
        errors.append("no rows and no empty-state message")
    if expected and EMPTY in text:
        errors.append("empty-state message shown with rows")

    errors += check_sitemap(out_dir / "sitemap.xml")

    index = out_dir / "index.html"
    if expected:
        home = PageReader()
        home.feed(index.read_text() if index.exists() else "")
        if "/upcoming" not in home.home_section_links:
            errors.append("the home 施行予定 section does not link to /upcoming")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Check the built /upcoming page.")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--data-dir", type=Path, default=SHIPPED)
    ap.add_argument("--today", default=None,
                    help="judge the build date against this day instead of the file's date")
    args = ap.parse_args()
    errors = check(args.out_dir, args.data_dir, args.today)
    for e in errors:
        print(e)
    print(f"{len(errors)} problem(s).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
