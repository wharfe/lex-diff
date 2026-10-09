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


def test_every_timeline_link_points_at_a_shipped_diff():
    # The site is a static export, so a diff_id with no file is a 404 that
    # the build never reports (#23).
    shipped = {p.stem for p in shipped_diffs()}
    for path in shipped_timelines():
        for entry in json.loads(path.read_text())["timeline"]:
            if entry.get("diff_id"):
                assert entry["diff_id"] in shipped, (path.name, entry["diff_id"])


def test_a_diffs_proposer_is_its_timeline_entrys():
    # enrich.py copies it by revision id instead of searching NDL by year,
    # and gives a diff that carries several same-day laws none at all.
    from enrich import diff_proposer

    timelines = {p.stem: json.loads(p.read_text()) for p in shipped_timelines()}
    for path in shipped_diffs():
        data = json.loads(path.read_text())
        assert data.get("proposer") == diff_proposer(
            data, timelines[data["law_id"]]
        ), path.name


# Published before same-day laws were named, and withheld from regeneration
# because a table changed in it (#28). Kept as it was by decision on #23.
KNOWN_SINGLE_TITLE_SAME_DAY = {"415AC0000000057_2025-03-31_2025-04-01"}


def test_a_diff_names_every_law_enforced_that_day():
    # Checked against the timeline, not against the diff's own field: a diff
    # whose re-annotation failed keeps its old single title, and every test
    # that reads only the diff would pass over it (#23 Gate 2 r3).
    timelines = {p.stem: json.loads(p.read_text()) for p in shipped_timelines()}
    for path in shipped_diffs():
        if path.stem in KNOWN_SINGLE_TITLE_SAME_DAY:
            continue
        data = json.loads(path.read_text())
        expected = {
            e["amendment_law_title"]
            for e in timelines[data["law_id"]]["timeline"]
            if e["enforcement_date"] == data["date_after"]
        }
        after = data["revision_after"]
        named = set(after.get("amendment_law_titles") or [after["amendment_law_title"]])
        assert named == expected, path.name


def test_the_known_exceptions_are_still_needed():
    # Once #28 regenerates it, the exception must go rather than linger.
    for stem in KNOWN_SINGLE_TITLE_SAME_DAY:
        assert (SHIPPED / f"{stem}.json").exists(), stem


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


def test_every_law_that_should_have_an_articles_file_has_one():
    """The SET of files, not their count.

    Every other check here is parametrized over the files that exist, so
    deleting ten of the eleven left the whole suite green: a test that vanishes
    with its data is not a guard. generateStaticParams() does not catch it
    either -- it only throws on an empty or duplicated param list.

    The expected set is derived from the shipped diffs, the same way
    test_shipped_articles_match_the_shipped_diffs derives each file's page set,
    so adding a law cannot make this red and no count is written down.
    労働基準法 322AC0000000049 has only 附則 changes, so collect_changes returns
    nothing for it and it falls out here without being named.
    """
    import articles

    files = shipped_articles()
    assert files, "no shipped articles/*.json at all"
    # One generation run writes them all, so they share an asof; max() picks it
    # without depending on the wall clock (an unenforced diff must stay out).
    asof = max(json.loads(p.read_text())["source"]["asof"] for p in files)
    expected = {
        law_id
        for law_id, docs in articles.shipped_diff_docs(SHIPPED).items()
        if articles.collect_changes(docs, asof)
    }
    assert {p.stem for p in files} == expected


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
    changes = articles.collect_changes(docs, doc["source"]["asof"])
    removed = set(doc.get("removed_articles", []))
    # An article may be missing only as one removed outright, which the latest
    # diff must itself call deleted (articles.resolve_current).
    for num in removed:
        assert changes[num][0]["type"] == "deleted", num
    assert {p["article_num"] for p in doc["articles"]} == set(changes) - removed


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_link_describes_only_a_target_whose_own_summary_survived(path):
    # The context line describes the TARGET article and was written when the
    # note was. It may stand only on positive evidence that the target still
    # reads that way: the target has a page AND that page passed the version
    # gate. A target with no page was never checked at all, and "not checked"
    # is not weaker than "checked and stale" -- it is the same claim with no
    # evidence behind it.
    doc = json.loads(path.read_text())
    by_slug = {p["slug"]: p for p in doc["articles"]}
    for page in doc["articles"]:
        for ref in page["related_articles"]:
            target = by_slug.get(ref["slug"]) if ref["slug"] else None
            if target is None or target["current_summary"] is None:
                assert ref["context"] == "", (page["article_num"], ref["ref"])
