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


def _doc(law_id, before, after, num, *, comment=None, gen="2026-10-12", main=3, ub=0):
    return {
        "law_id": law_id, "law_title": f"{law_id}法", "date_after": after,
        "stats": {"main": main},
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


def render(data_dir, *, build_date=TODAY, drop=None, extra_link=None, move=None,
           heading=None, empty_month=False, title=c.TITLE, swap_text=None,
           unfixed_last=True, lastmod=False, home_link=True, canonical="/upcoming",
           og_type="website", empty_msg=False, mains=1, rows_override=None):
    rows = rows_override if rows_override is not None else c.expected_rows(data_dir, build_date)
    groups: dict[str, list[str]] = {}
    for pid, x in sorted(rows.items(), key=lambda kv: (kv[1]["date"], kv[0])):
        if pid == drop:
            continue
        where = "unfixed" if pid == move else x["where"]
        groups.setdefault(where, []).append(pid)
    if empty_month:
        groups["2027-07"] = []
    keys = sorted(k for k in groups if k != "unfixed")
    if "unfixed" in groups:
        keys = keys + ["unfixed"] if unfixed_last else ["unfixed"] + keys
    body = f"<div data-build-date=\"{build_date}\"><h1>施行予定の法改正一覧</h1><p>{c.INTRO}</p><p>{c.SCOPE}</p>"
    for k in keys:
        h = c.UNFIXED_HEADING if k == "unfixed" else c.month_heading(k)
        if k == keys[0] and heading:
            h = heading
        body += f'<section data-upcoming-section="{k}"><h2>{h}</h2>'
        for pid in groups[k]:
            texts = list(rows[pid]["texts"])
            if swap_text == pid:
                texts[-1] = "本則は変わらない" if "本則は変わらない" not in texts else "施行されると本則 9 条が変わる"
            body += (f'<a href="/diff/{pid}" data-pending-id="{pid}">'
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
    html = f"<html><head>{head}</head><body>" + "<main>" * mains + body + "</main>" * mains + "</body></html>"
    out = data_dir.parent / "out"
    out.mkdir(exist_ok=True)
    (out / "upcoming.html").write_text(html)
    sm = f"<url><loc>{c.BASE}/upcoming</loc>" + ("<lastmod>2026-10-12</lastmod>" if lastmod else "") + "</url>"
    (out / "sitemap.xml").write_text(sm)
    home = '<section data-home-upcoming=""><a href="/upcoming">すべて見る</a></section>' if home_link \
        else '<nav><a href="/upcoming">x</a></nav>'
    (out / "index.html").write_text(home)
    return c.check(out, data_dir, TODAY)


def test_the_correct_page_passes(data_dir):
    assert render(data_dir) == []


FIRST = "A_2026-11-30_2026-12-01"


@pytest.mark.parametrize("defect", [
    {"drop": FIRST},                                   # a row missing
    {"extra_link": FIRST},                             # a second link to a row
    {"extra_link": "E_2026-10-01_2026-10-02"},         # an overdue diff linked
    {"move": FIRST},                                   # a fixed-date row under unfixed
    {"heading": "2026年12月に施行"},                    # wrong heading text
    {"empty_month": True},                             # an empty month section
    {"title": "2026年12月に施行される法改正 | lexdiff"},  # a month in the title
    {"swap_text": FIRST},                              # a row's stats text wrong
    {"unfixed_last": False},                           # unfixed section not last
    {"lastmod": True},                                 # a lastmod on /upcoming
    {"home_link": False},                              # home link outside the section
    {"canonical": "/"},                                # canonical points home
    {"og_type": "article"},                            # OG replaced, not restated
    {"empty_msg": True},                               # empty message beside rows
    {"mains": 2},                                      # page renders its own <main>
    {"build_date": "2026-10-10"},                      # a stale build date
], ids=lambda d: next(iter(d)))
def test_each_defect_is_reported(data_dir, defect):
    assert render(data_dir, **defect), defect


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
    assert any("先に施行予定の改正 2 件" in t for t in rows[FIRST]["texts"])
    assert c.month_heading("2027-01") == "施行日が2027年1月の改正"
