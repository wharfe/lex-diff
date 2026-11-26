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
    head = (f"<title>{title}</title><meta name=\"description\" content=\"{c.upcoming_description(rows)}\"/>"
            f"<link rel=\"canonical\" href=\"{c.BASE}{canonical}\"/>"
            f"<meta property=\"og:title\" content=\"{c.TITLE}\"/>"
            f"<meta property=\"og:description\" content=\"{c.upcoming_description(rows)}\"/>"
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


# #51: the descriptions and pending diff titles are built from the data.

def test_the_upcoming_description_names_the_rows_laws(data_dir):
    rows = c.expected_rows(data_dir, TODAY)
    assert c.upcoming_description(rows) == (
        c.DESCRIPTION_HEAD + "A法、B法、C法ほか1法令の改正を載せています。" + c.DESCRIPTION_TAIL)
    assert c.upcoming_description({}) == c.DESCRIPTION_HEAD + c.DESCRIPTION_TAIL
    # Rows of one law name it once.
    one = {k: {**v, "law_title": "X法"} for k, v in rows.items()}
    assert c.upcoming_description(one) == c.DESCRIPTION_HEAD + "X法の改正を載せています。" + c.DESCRIPTION_TAIL


def test_the_upcoming_description_has_no_date(data_dir):
    import re
    desc = c.upcoming_description(c.expected_rows(data_dir, TODAY))
    assert not re.search(r"\d{4}|[0-9０-９]+月|令和|平成", desc), desc


def test_a_stale_upcoming_description_is_reported(data_dir):
    errors = render(data_dir, meta={"description": c.DESCRIPTION_HEAD + c.DESCRIPTION_TAIL + "x"})
    assert any("meta description" in e for e in errors), errors


CH2 = "第二章\u3000禁止等"
CH3 = "第三章\u3000措置等"
CH5 = "第五章\u3000罰則"


def _pending_diff(*, comment=None, entries=None, suppl=1):
    entries = entries if entries is not None else (
        [("modified", [CH2])] * 3 + [("added", [CH3])] * 2 + [("modified", [CH3]), ("added", [CH5])])
    return {
        "law_title": "甲法", "date_after": "2026-12-01",
        "diffs": [{"type": t, "is_suppl": False, "section_path": sp} for t, sp in entries]
                 + [{"type": "added", "is_suppl": True, "section_path": []}] * suppl,
        "pending": {
            "generated_on": "2026-11-06",
            "revisions": [{"law_revision_id": "x", "amendment_law_num": "令和七年法律第一号",
                           "enforcement_comment": comment}],
            "unenforced_before": [],
        },
    }


def test_a_fixed_date_goes_in_the_diff_title():
    doc = _pending_diff()
    # CH3 has as many entries as CH2 (3 each) but appears later: ties keep order.
    assert c.diff_page_title(doc) == "甲法の改正【施行日 2026-12-01】本則7条: 禁止等・措置等ほか | lexdiff"
    assert c.diff_page_description(doc) == (
        "甲法の改正（令和七年法律第一号）で変わる条文の新旧対照。施行日: 2026-12-01。"
        "施行されると本則7条が変わります（うち新設3条）。"
        f"主な変更箇所: {CH2}、{CH3}ほか。2026-11-06時点で未施行。")


def test_an_unfixed_date_stays_out_of_the_diff_title():
    doc = _pending_diff(comment="政令で定める日", entries=[("modified", [CH5])])
    assert c.diff_page_title(doc) == "甲法の改正【施行日未確定】本則1条: 罰則 | lexdiff"
    assert "2026" not in c.diff_page_title(doc)
    # The description quotes e-Gov's own wording with the date it records.
    assert "施行日: 政令で定める日（e-Gov 上の予定日: 2026-12-01）。" in c.diff_page_description(doc)


def test_more_entries_rank_a_chapter_first():
    doc = _pending_diff(entries=[("modified", [CH2]), ("modified", [CH3]), ("modified", [CH3])])
    assert c.diff_page_title(doc).endswith("本則3条: 措置等・禁止等 | lexdiff")


def test_a_diff_without_chapters_or_main_changes():
    flat = _pending_diff(entries=[("modified", [])])
    assert c.diff_page_title(flat) == "甲法の改正【施行日 2026-12-01】本則1条 | lexdiff"
    assert "主な変更箇所" not in c.diff_page_description(flat)
    suppl = _pending_diff(entries=[], suppl=2)
    assert c.diff_page_title(suppl) == "甲法の改正【施行日 2026-12-01】附則のみの改正 | lexdiff"
    assert "施行されると附則2件が変わります（本則は変わりません）。" in c.diff_page_description(suppl)


def _diff_page(out, stem, title, description, og_title=None, og_description=None):
    d = out / "diff"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.html").write_text(
        f'<html><head><title>{title}</title><meta name="description" content="{description}"/>'
        f'<meta property="og:title" content="{og_title or title}"/>'
        f'<meta property="og:description" content="{og_description or description}"/></head></html>')


@pytest.fixture
def diff_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    doc = _pending_diff()
    (d / "X_2026-11-30_2026-12-01.json").write_text(json.dumps(doc, ensure_ascii=False))
    (d / "Y_2025-03-31_2025-04-01.json").write_text(json.dumps({"date_after": "2025-04-01"}))
    return d, doc


STEM = "X_2026-11-30_2026-12-01"


def test_a_correct_diff_page_passes(diff_dir):
    d, doc = diff_dir
    out = d.parent / "out"
    _diff_page(out, STEM, c.diff_page_title(doc), c.diff_page_description(doc))
    assert c.check_diff_pages(out, d) == []


@pytest.mark.parametrize("field,expected", [
    ("title", f"{STEM}: title"),
    ("description", f"{STEM}: meta description"),
    ("og_title", f"{STEM}: meta og:title"),
    ("og_description", f"{STEM}: meta og:description"),
])
def test_each_wrong_diff_page_field_is_reported(diff_dir, field, expected):
    d, doc = diff_dir
    out = d.parent / "out"
    fields = {"title": c.diff_page_title(doc), "description": c.diff_page_description(doc)}
    # The base tree's wording: the generated_on claim and law number, no date.
    old = "甲法【2026-11-06時点で未施行】令和七年法律第一号による改正 | lexdiff"
    _diff_page(out, STEM, **{**fields, field: old})
    errors = c.check_diff_pages(out, d)
    assert any(expected in e for e in errors), errors


def test_a_missing_diff_page_is_reported(diff_dir):
    d, _ = diff_dir
    errors = c.check_diff_pages(d.parent / "out", d)
    assert any("does not exist" in e for e in errors), errors


# Gate3 round 1 (codex, code-review, intent review).

def test_the_upcoming_description_follows_the_page_order():
    # The unfixed section comes last on the page, whatever its date.
    rows = {
        "U_2026-10-31_2026-11-01": {"date": "2026-11-01", "where": "unfixed", "law_title": "U法"},
        "A_2026-11-30_2026-12-01": {"date": "2026-12-01", "where": "2026-12", "law_title": "A法"},
    }
    assert c.upcoming_description(rows) == (
        c.DESCRIPTION_HEAD + "A法、U法の改正を載せています。" + c.DESCRIPTION_TAIL)


def test_an_empty_heading_is_not_a_place():
    doc = _pending_diff(entries=[("modified", [""])])
    assert c.diff_page_title(doc) == "甲法の改正【施行日 2026-12-01】本則1条 | lexdiff"
    assert "主な変更箇所" not in c.diff_page_description(doc)


def test_two_pending_pages_with_one_title_are_reported(diff_dir):
    d, doc = diff_dir
    other = "X_2027-11-30_2027-12-01"
    (d / f"{other}.json").write_text(json.dumps(doc, ensure_ascii=False))
    out = d.parent / "out"
    for stem in (STEM, other):
        _diff_page(out, stem, c.diff_page_title(doc), c.diff_page_description(doc))
    errors = c.check_diff_pages(out, d)
    assert any("share the title" in e for e in errors), errors
