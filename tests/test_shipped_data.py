"""Integration-level guards on what actually ships.

The other test files check the pure functions, which proves the helpers are
right and not that the published data agrees with them. These read
`frontend/public/data/` — the bytes readers actually get — and fail when it
drifts from what the current code would produce.

What they do NOT cover: the producer wiring. Deleting the `compute_stats(diffs)`
call in `diff.py` leaves these green, because the shipped JSON is only rewritten
when the pipeline runs. Pinning that needs a fixture-driven run of `diff.main()`
(issue #15). The `law_summary.main()` path is covered, in
test_law_summary_validation.py.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from diff import compute_stats
from law_summary import validate_summary_shape

SHIPPED = Path(__file__).parent.parent / "frontend" / "public" / "data"


def shipped_diffs():
    return sorted(p for p in SHIPPED.glob("*_*-*-*_*-*-*.json"))


def shipped_timelines():
    return sorted((SHIPPED / "timelines").glob("*.json"))


def test_shipped_diff_files_are_present():
    # A glob that quietly matches nothing would make every test below vacuous.
    assert len(shipped_diffs()) >= 16


def test_shipped_timeline_files_are_present():
    assert len(shipped_timelines()) >= 12


@pytest.mark.parametrize("path", shipped_diffs(), ids=lambda p: p.name)
def test_shipped_stats_match_compute_stats(path):
    data = json.loads(path.read_text())
    assert data["stats"] == compute_stats(data["diffs"]), (
        f"{path.name}: stats disagree with compute_stats — regenerate or migrate it"
    )


@pytest.mark.parametrize("path", shipped_timelines(), ids=lambda p: p.name)
def test_shipped_law_summaries_are_valid(path):
    summary = json.loads(path.read_text()).get("summary")
    # Every shipped law must have one. This used to skip when summary was None,
    # because four laws (民法・道路交通法・労働基準法・著作権法 — the biggest ones)
    # had never had law_summary.py run over them at all and shipped a /law page
    # with no overview block, issue #14. Closing that issue means the gap
    # cannot reopen silently the next time a law is added.
    assert summary is not None, f"{path.name}: no summary — run law_summary.py"
    assert validate_summary_shape(summary) == [], f"{path.name}: {validate_summary_shape(summary)}"


import datetime

ARTICLES_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data" / "articles"


def shipped_articles():
    return sorted(ARTICLES_DIR.glob("*.json"))


def test_shipped_article_files_are_present():
    # Without this, every test below passes vacuously on an empty glob.
    assert len(shipped_articles()) >= 1


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_shipped_articles_pass_validate_articles(path):
    import articles

    assert articles.validate_articles(json.loads(path.read_text())) == []


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_shipped_article_source_records_one_run(path):
    source = json.loads(path.read_text())["source"]
    fetched = datetime.datetime.fromisoformat(source["fetched_at"])
    assert fetched.tzinfo is not None
    assert fetched.utcoffset() == datetime.timedelta(hours=9)
    assert fetched.date().isoformat() == source["asof"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_shipped_summary_means_the_text_still_matched(path):
    """The version gate, re-run on the bytes that ship.

    Checking only for abolished penalty names would let 著作権法122条の2 through:
    its note is about 秘密保持命令 while today's article is about 帳簿, and
    neither string contains a penalty name. The comparison has to be the same
    one the generator made, so it is made again here from the shipped diffs.
    """
    import articles

    doc = json.loads(path.read_text())
    docs = articles.shipped_diff_docs(ARTICLES_DIR.parent)[doc["law_id"]]
    changes = articles.collect_changes(docs, doc["source"]["asof"])
    for page in doc["articles"]:
        if page["current_summary"] is None:
            continue
        latest = changes[page["article_num"]][0]
        current = page["current"]["paragraphs"]
        assert articles.texts_match(latest["paragraphs_after"], current), page["article_num"]
        text = "".join(p["text"] for p in current)
        assert articles.summary_is_safe(page["current_summary"]["text"], text), page["article_num"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_shipped_deleted_article_carries_its_former_text(path):
    # Keyed on the page being a tombstone, not on the amendment's type. The
    # type was the hole: e-Gov records some repeals as a modification that
    # replaces the body with 削除, so 民法733/746 and 刑法178 shipped as
    # `present` with a present-tense summary and live links, and this test
    # skipped every one of them.
    import articles

    doc = json.loads(path.read_text())
    for page in doc["articles"]:
        body = "".join(p["text"] for p in page["current"]["paragraphs"]).strip()
        status = page["current"]["status"]
        if body != "削除" and status not in articles.TOMBSTONE_STATUSES:
            continue
        # Each side implies the other: a 削除 body is a tombstone, and a
        # tombstone's body is 削除.
        assert status in articles.TOMBSTONE_STATUSES, page["article_num"]
        assert body == "削除", page["article_num"]
        assert page["former"] and page["former"]["paragraphs"], page["article_num"]
        assert page["current_summary"] is None, page["article_num"]
        assert page["related_articles"] == [], page["article_num"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_page_without_a_current_summary_shows_no_current_links(path):
    # spec §4: the gate covers the related-article links too, not just prose.
    doc = json.loads(path.read_text())
    for page in doc["articles"]:
        if page["current_summary"] is None:
            assert page["related_articles"] == [], page["article_num"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_shipped_articles_match_the_shipped_diffs(path):
    # The page set is derived, not a magic number.
    import articles

    doc = json.loads(path.read_text())
    docs = articles.shipped_diff_docs(ARTICLES_DIR.parent)[doc["law_id"]]
    expected = set(articles.collect_changes(docs, doc["source"]["asof"]))
    assert {p["article_num"] for p in doc["articles"]} == expected


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_link_describes_only_a_target_whose_own_summary_survived(path):
    # The context line describes the TARGET article and was written when the
    # note was. If the target's own page could not keep its summary, that line
    # is making the claim the target's page refused to make.
    doc = json.loads(path.read_text())
    by_slug = {p["slug"]: p for p in doc["articles"]}
    for page in doc["articles"]:
        for ref in page["related_articles"]:
            target = by_slug.get(ref["slug"]) if ref["slug"] else None
            if target is not None and target["current_summary"] is None:
                assert ref["context"] == "", (page["article_num"], ref["ref"])
