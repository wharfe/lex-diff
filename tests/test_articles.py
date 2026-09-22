# tests/test_articles.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import articles


@pytest.mark.parametrize(
    "num,slug",
    [("306", "306"), ("308_2", "308-2"), ("117_2_2", "117-2-2")],
)
def test_article_slug(num, slug):
    assert articles.article_slug(num) == slug


def test_article_slug_rejects_a_range_num():
    # 753:754 is e-Gov's element id for "第七百五十三条及び第七百五十四条", not an
    # article number. Nobody searches for it, and it must never become a URL.
    with pytest.raises(ValueError):
        articles.article_slug("753:754")


@pytest.mark.parametrize(
    "num,shown",
    [("306", "第306条"), ("308_2", "第308条の2"), ("117_2_2", "第117条の2の2")],
)
def test_display_num(num, shown):
    assert articles.display_num(num) == shown


def test_range_members():
    assert articles.range_members("753:754") == ["753", "754"]


def test_range_members_rejects_a_non_numeric_endpoint():
    with pytest.raises(ValueError):
        articles.range_members("753:754_2")


def _entry(num, type_="modified", suppl=False, **over):
    entry = {
        "type": type_,
        "article_num": num,
        "title_before": f"第{num}条",
        "title_after": f"第{num}条",
        "section_path": ["第二編　物権"],
        "paragraphs_before": [{"num": "1", "text": "旧"}],
        "paragraphs_after": [{"num": "1", "text": "新"}],
        "is_suppl": suppl,
        "annotation": {
            "plain_summary": f"{num} の説明",
            "change_description": f"{num} が変わった",
            "cross_references": [],
        },
    }
    entry.update(over)
    return entry


def _doc(date_after, entries, law_id="129AC0000000089", date_before="2026-03-31"):
    return {
        "law_id": law_id,
        "law_title": "民法",
        "date_before": date_before,
        "date_after": date_after,
        "revision_after": {"amendment_law_title": "民法等の一部を改正する法律"},
        "diffs": entries,
        "_diff_id": f"{law_id}_{date_before}_{date_after}",
    }


def test_suppl_entries_never_become_pages():
    changes = articles.collect_changes(
        [_doc("2026-04-01", [_entry("306"), _entry("1", suppl=True)])], "2026-09-22"
    )
    assert set(changes) == {"306"}


def test_unenforced_diffs_are_skipped():
    changes = articles.collect_changes(
        [_doc("2026-04-01", [_entry("306")]), _doc("2099-01-01", [_entry("999")])],
        "2026-09-22",
    )
    assert set(changes) == {"306"}


def test_changes_are_newest_first():
    docs = [
        _doc("2024-11-01", [_entry("117_2_2")]),
        _doc("2026-04-01", [_entry("117_2_2")]),
    ]
    dates = [c["enforcement_date"] for c in articles.collect_changes(docs, "2026-09-22")["117_2_2"]]
    assert dates == ["2026-04-01", "2024-11-01"]


def test_a_range_entry_is_dropped_when_its_members_have_their_own_entries():
    # 753:754 carries a plain_summary written about 754 only. Spreading it over
    # 753 would make that page claim 753 is about 夫婦間契約取消権.
    docs = [
        _doc(
            "2026-04-01",
            [
                _entry("753", "deleted"),
                _entry("754", "deleted"),
                _entry("753:754", "added"),
            ],
        )
    ]
    changes = articles.collect_changes(docs, "2026-09-22")
    assert set(changes) == {"753", "754"}
    assert all(c["type"] == "deleted" for cs in changes.values() for c in cs)


def test_a_range_entry_without_member_entries_raises():
    # Do not silently expand it. A range we do not already understand means the
    # law's structure is not what this script assumes.
    docs = [_doc("2026-04-01", [_entry("753:754", "added")])]
    with pytest.raises(ValueError, match="753:754"):
        articles.collect_changes(docs, "2026-09-22")
