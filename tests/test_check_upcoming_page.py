"""The /upcoming checker must go red on each defect it exists to catch.

The checker reads built HTML, which CI never builds for it, so these fixtures
are the only standing proof that it is not vacuous (docs/upcoming-page/spec.md).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import check_upcoming_page as c

TODAY = "2026-10-18"


def _doc(law_id: str, before: str, after: str, num: str, *, comment: str | None = None,
         gen: str = "2026-10-12", main: int = 3, ub: int = 0) -> dict:
    return {
        "law_id": law_id, "law_title": f"{law_id}法", "date_after": after,
        "stats": {"main": main},
        "diffs": [{"is_suppl": False}] * main + [{"is_suppl": True}],
        "pending": {
            "generated_on": gen,
            "revisions": [{"law_revision_id": f"{law_id}_x", "amendment_law_num": num,
                           "amendment_law_title": "改正法", "enforcement_comment": comment}],
            "unenforced_before": [{"law_revision_id": f"u{i}"} for i in range(ub)],
        },
    }


DOCS = {
    "A_2026-11-30_2026-12-01": _doc("A", "2026-11-30", "2026-12-01", "令和七年法律第一号", ub=2),
    "B_2026-12-14_2026-12-15": _doc("B", "2026-12-14", "2026-12-15", "令和七年法律第二号", main=0),
    "C_2027-01-16_2027-01-17": _doc("C", "2027-01-16", "2027-01-17", "令和八年法律第三号", gen="2026-10-18"),
    "D_2028-06-12_2028-06-13": _doc("D", "2028-06-12", "2028-06-13", "令和八年法律第四号",
                                    comment="政令で定める日"),
    "E_2026-10-01_2026-10-02": _doc("E", "2026-10-01", "2026-10-02", "令和八年法律第五号"),  # overdue
}


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    for stem, doc in DOCS.items():
        (d / f"{stem}.json").write_text(json.dumps(doc, ensure_ascii=False))
    (d / "F_2025-03-31_2025-04-01.json").write_text(json.dumps({"date_after": "2025-04-01"}))
    return d


def render(data_dir, *, build_date=TODAY, drop=None, extra_link=None, move=None, to_month=None,
           heading=None, empty_month=False, title=c.TITLE, swap_text=None, extra_text=None,
           unfixed_last=True, lastmod=False, home_link=True, canonical="/upcoming",
           og_type="website", empty_msg=False, mains=1, rows_override=None,
           meta=None, drop_text=None, reverse_month=None, bad_href=None, sitemap=True,
           build_dates=1):
    rows = rows_override if rows_override is not None else c.expected_rows(data_dir, build_date)
    groups: dict[str, list[str]] = {}
    for pid, x in sorted(rows.items(), key=lambda kv: (kv[1]["date"], kv[0])):
        if pid == drop:
            continue
        where = "unfixed" if pid == move else x["where"]
        if pid == UNFIXED and to_month:
            where = to_month
        groups.setdefault(where, []).append(pid)
    if empty_month:
        groups["2027-07"] = []
    keys = sorted(k for k in groups if k != "unfixed")
    if "unfixed" in groups:
        keys = keys + ["unfixed"] if unfixed_last else ["unfixed"] + keys
    if reverse_month in groups:
        groups[reverse_month].reverse()
    intro = "" if drop_text == "intro" else c.INTRO
    scope = "" if drop_text == "scope" else c.SCOPE
    marks = "".join(f'<span data-build-date="{build_date}"></span>' for _ in range(build_dates - 1))
    body = f"<div data-build-date=\"{build_date}\">{marks}<h1>施行予定の法改正一覧</h1><p>{intro}</p><p>{scope}</p>"
    for k in keys:
        h = c.UNFIXED_HEADING if k == "unfixed" else c.month_heading(k)
        if k == keys[0] and heading:
            h = heading
        body += f'<section data-upcoming-section="{k}"><h2>{h}</h2>'
        for pid in groups[k]:
            texts = list(rows[pid]["texts"])
            if swap_text == pid:      # texts[4] is the stats label (page order)
                texts[4] = "本則は変わらない" if texts[4] != "本則は変わらない" else "施行されると本則 9 条が変わる"
            if extra_text == pid:     # the right text plus a contradicting one
                texts.insert(5, "本則は変わらない")
            href = f"/diff/{pid}x" if pid == bad_href else f"/diff/{pid}"
            body += (f'<a href="{href}" data-pending-id="{pid}">'
                     + "<!-- -->".join(f"<span>{t}</span>" for t in texts) + "</a>")
        body += "</section>"
    if extra_link:
        body += f'<a href="/diff/{extra_link}">x</a>'
    if not rows or empty_msg:
        body += f"<p>{c.EMPTY}</p>"
    body += "</div>"
    head = (f"<title>{title}</title><meta name=\"description\" content=\"{c.DESCRIPTION}\"/>"
            f"<link rel=\"canonical\" href=\"{c.BASE}{canonical}\"/>"
            f"<meta property=\"og:title\" content=\"{c.TITLE}\"/>"
            f"<meta property=\"og:description\" content=\"{c.DESCRIPTION}\"/>"
            f"<meta property=\"og:url\" content=\"{c.BASE}/upcoming\"/>"
            f"<meta property=\"og:site_name\" content=\"lexdiff\"/>"
            f"<meta property=\"og:locale\" content=\"ja_JP\"/>"
            f"<meta property=\"og:type\" content=\"{og_type}\"/>")
    for key, value in (meta or {}).items():
        head = head.replace(f'"{key}" content="', f'"{key}" content="{value}', 1)
    html = f"<html><head>{head}</head><body>" + "<main>" * mains + body + "</main>" * mains + "</body></html>"
    out = data_dir.parent / "out"
    out.mkdir(exist_ok=True)
    (out / "upcoming.html").write_text(html)
    sm = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          f"<url><loc>{c.BASE}/upcoming</loc>" + ("<lastmod>2026-10-12</lastmod>" if lastmod else "")
          + "</url></urlset>")
    (out / "sitemap.xml").write_text(sm if sitemap else sm.replace("/upcoming", "/about"))
    home = '<section data-home-upcoming=""><a href="/upcoming">すべて見る</a></section>' if home_link \
        else '<nav><a href="/upcoming">x</a></nav>'
    (out / "index.html").write_text(home)
    return c.check(out, data_dir, TODAY)


def test_the_correct_page_passes(data_dir):
    assert render(data_dir) == []


FIRST = "A_2026-11-30_2026-12-01"
UNFIXED = "D_2028-06-12_2028-06-13"


# Each defect with the error it must raise: a fixture caught by some other
# check proves nothing about its own (code-review, Gate3).
DEFECTS = [
    ({"drop": FIRST}, "missing ['A_"),
    ({"extra_link": FIRST}, "repeated ['A_"),
    ({"extra_link": "E_2026-10-01_2026-10-02"}, "extra ['E_"),
    ({"move": FIRST}, f"{FIRST}: in section 'unfixed'"),
    ({"to_month": "2028-06"}, f"{UNFIXED}: in section '2028-06'"),
    ({"heading": "2026年12月に施行"}, "heading '2026年12月に施行'"),
    ({"empty_month": True}, "'2027-07'"),
    ({"unfixed_last": False}, "sections ['unfixed'"),
    ({"reverse_month": "2026-12"}, "not in date→id order"),
    ({"swap_text": FIRST}, f"{FIRST}: row text"),
    ({"extra_text": FIRST}, f"{FIRST}: row text"),
    ({"bad_href": FIRST}, f"{FIRST}: href"),
    ({"title": "2026年12月に施行される法改正 | lexdiff"}, "title '"),
    ({"meta": {"description": "x"}}, "meta description"),
    ({"meta": {"og:title": "x"}}, "meta og:title"),
    ({"meta": {"og:description": "x"}}, "meta og:description"),
    ({"meta": {"og:url": "x"}}, "meta og:url"),
    ({"meta": {"og:site_name": "x"}}, "meta og:site_name"),
    ({"meta": {"og:locale": "x"}}, "meta og:locale"),
    ({"og_type": "article"}, "meta og:type"),
    ({"canonical": "/"}, "canonical"),
    ({"drop_text": "intro"}, "missing text: 成立済み"),
    ({"drop_text": "scope"}, "missing text: lexdiff"),
    ({"empty_msg": True}, "empty-state message shown"),
    ({"mains": 2}, "2 <main>"),
    ({"build_date": "2026-10-10"}, "is neither"),
    ({"build_date": "2026-10-17"}, "precedes a generated_on"),
    ({"build_dates": 2}, "expected one data-build-date"),
    ({"lastmod": True}, "gives /upcoming a lastmod"),
    ({"sitemap": False}, "lists /upcoming 0 times"),
    ({"home_link": False}, "home 施行予定 section"),
]


@pytest.mark.parametrize("defect,expected", DEFECTS,
                         ids=[f"{next(iter(d))}={d[next(iter(d))]}" for d, _ in DEFECTS])
def test_each_defect_raises_its_own_error(data_dir, defect, expected):
    errors = render(data_dir, **defect)
    assert any(expected in e for e in errors), errors


def test_an_empty_page_needs_its_message(data_dir):
    for p in data_dir.glob("*.json"):
        p.unlink()
    assert render(data_dir) == []
    out = data_dir.parent / "out" / "upcoming.html"
    out.write_text(out.read_text().replace(c.EMPTY, ""))
    assert c.check(out.parent, data_dir, TODAY)


def test_the_expected_rows_follow_the_spec(data_dir):
    rows = c.expected_rows(data_dir, TODAY)
    assert "E_2026-10-01_2026-10-02" not in rows             # overdue
    assert rows["D_2028-06-12_2028-06-13"]["where"] == "unfixed"
    assert rows[FIRST]["where"] == "2026-12"
    assert any("時点で未施行の他の改正 2 件" in t for t in rows[FIRST]["texts"])
    assert c.month_heading("2027-01") == "施行日が2027年1月の改正"


# codex Gate3: three ways the first checker passed a wrong page.

def test_rows_without_their_marker_are_reported(data_dir):
    render(data_dir)
    out = data_dir.parent / "out"
    page = out / "upcoming.html"
    page.write_text(page.read_text().replace(" data-pending-id=", " data-x="))
    assert c.check(out, data_dir, TODAY)


def test_a_nested_section_does_not_end_the_home_section(data_dir):
    assert render(data_dir) == []
    out = data_dir.parent / "out"
    (out / "index.html").write_text(
        '<section data-home-upcoming=""><section><p>x</p></section>'
        '<a href="/upcoming">すべて見る</a></section>')
    assert c.check(out, data_dir, TODAY) == []


def test_a_lastmod_before_loc_is_reported(data_dir):
    render(data_dir)
    out = data_dir.parent / "out"
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><lastmod>2026-10-12</lastmod><loc>{c.BASE}/upcoming</loc></url></urlset>")
    assert c.check(out, data_dir, TODAY)


def test_the_build_date_is_judged_against_the_files_own_date(data_dir):
    # Spec: 「HTML の更新日（JST）か前日」, not the day the checker runs
    # (Layer 3, Gate3): a check run two days after the build is not a defect.
    import os
    from datetime import datetime
    assert render(data_dir) == []
    out = data_dir.parent / "out"
    page = out / "upcoming.html"
    stamp = datetime(2026, 10, 18, 12, tzinfo=c.JST).timestamp()
    os.utime(page, (stamp, stamp))
    assert c.check(out, data_dir, None) == []
    later = datetime(2026, 10, 25, 12, tzinfo=c.JST).timestamp()
    os.utime(page, (later, later))
    assert c.check(out, data_dir, None)
