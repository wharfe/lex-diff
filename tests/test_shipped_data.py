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
        # Compared as sorted lists, not sets: two different laws can share a
        # title on one day, and a set would let one stale title pass for both.
        expected = sorted(
            e["amendment_law_title"]
            for e in timelines[data["law_id"]]["timeline"]
            if e["enforcement_date"] == data["date_after"]
        )
        after = data["revision_after"]
        named = sorted(after.get("amendment_law_titles") or [after["amendment_law_title"]])
        assert named == expected, path.name


def test_the_known_exceptions_are_still_needed():
    # Once #28 regenerates it, the exception must go rather than linger.
    # Existing is not enough: #28 regenerates it under the same name.
    for stem in KNOWN_SINGLE_TITLE_SAME_DAY:
        path = SHIPPED / f"{stem}.json"
        assert path.exists(), stem
        after = json.loads(path.read_text())["revision_after"]
        assert "amendment_law_titles" not in after, f"{stem}: drop the exception"


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


def former_disagreements(doc, diff_docs):
    """Pages whose former block and top history card tell different stories (#26).

    Re-derived from the shipped diffs rather than read back through
    validate_articles: the latest change is collect_changes' first entry at the
    file's own asof (never the wall clock -- a pending diff rebuilt later would
    otherwise enter the history), and its basis is decided again on its text.
    """
    import articles

    history = articles.collect_changes(diff_docs, doc["source"]["asof"])
    problems = []
    for page in doc["articles"]:
        num = page["article_num"]
        if num not in history or not page["changes"]:
            problems.append(f"{num}: no history to compare against")
            continue
        latest = history[num][0]
        card = page["changes"][0]
        if card["diff_id"] != latest["diff_id"]:
            problems.append(f"{num}: the top card is {card['diff_id']}, the latest diff {latest['diff_id']}")
            continue
        if card["summary_basis"] != latest["summary_basis"]:
            problems.append(f"{num}: the top card says {card['summary_basis']}, its diff {latest['summary_basis']}")
        before = latest["summary_basis"] == articles.SUMMARY_BASIS_BEFORE
        if (page["former"] is not None) != before:
            problems.append(f"{num}: former is {page['former'] is not None} under a {latest['summary_basis']} change")
        elif before and (
            page["former"]["as_of"] != latest["date_before"]
            or page["former"]["paragraphs"] != latest["paragraphs_before"]
        ):
            # 「今回の改正直前の条文」 must be the text just before THIS change.
            problems.append(f"{num}: former is not the text before {latest['diff_id']}")
    return problems


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_shipped_former_block_goes_with_a_latest_change_about_the_text_before(path):
    import articles

    doc = json.loads(path.read_text())
    diff_docs = articles.shipped_diff_docs(ARTICLES_DIR.parent)[doc["law_id"]]
    assert former_disagreements(doc, diff_docs) == []


def test_the_shipped_former_check_sees_both_kinds_of_page():
    # Most laws have no tombstone at all, so the per-file check above could go
    # on passing over data in which no page ever carried a former block.
    kinds = {
        page["former"] is not None
        for path in shipped_articles()
        for page in json.loads(path.read_text())["articles"]
    }
    assert kinds == {True, False}


def test_the_shipped_former_check_catches_a_page_broken_either_way():
    """The per-file check only ever sees agreeing data; this is its red, kept.

    Broken on both sides, one page per branch. The diff side matters: a check
    that compared a page only with itself would catch the page-side breaks and
    none of the diff-side ones.
    """
    import copy

    import articles

    doc = next(
        d for d in (json.loads(p.read_text()) for p in shipped_articles())
        if sum(page["former"] is not None for page in d["articles"]) >= 3
    )
    diff_docs = articles.shipped_diff_docs(ARTICLES_DIR.parent)[doc["law_id"]]
    assert former_disagreements(doc, diff_docs) == []
    latest = {
        num: history[0]["diff_id"]
        for num, history in articles.collect_changes(diff_docs, doc["source"]["asof"]).items()
    }

    broken, broken_diffs = copy.deepcopy(doc), copy.deepcopy(diff_docs)
    tombs = [p for p in broken["articles"] if p["former"] is not None]
    plain = [p for p in broken["articles"] if p["former"] is None]
    # Page side: the former block moved from a repealed article to a standing one.
    plain[0]["former"], tombs[0]["former"] = tombs[0]["former"], None
    # Page side: a former block from some other version than its latest diff's.
    tombs[1]["former"]["as_of"] = "1900-01-01"
    tombs[2]["former"]["paragraphs"] = [{"num": "1", "text": "別の版の本文"}]
    # Diff side: the latest diff now repeals the article; the page was not rebuilt.
    relabelled = plain[1]["article_num"]
    diff = next(d for d in broken_diffs if d["_diff_id"] == latest[relabelled])
    entry = next(e for e in diff["diffs"] if e["article_num"] == relabelled and not e.get("is_suppl"))
    entry["paragraphs_after"] = [{"num": "1", "text": "削除"}]
    # The top card is not the latest diff at all.
    plain[2]["changes"][0]["diff_id"] = "not-a-shipped-diff"

    t0, t1, t2 = (p["article_num"] for p in tombs[:3])
    p0, p2 = plain[0]["article_num"], plain[2]["article_num"]
    assert sorted(former_disagreements(broken, broken_diffs)) == sorted([
        f"{t0}: former is False under a before change",
        f"{p0}: former is True under a after change",
        f"{t1}: former is not the text before {latest[t1]}",
        f"{t2}: former is not the text before {latest[t2]}",
        f"{relabelled}: the top card says after, its diff before",
        f"{relabelled}: former is False under a before change",
        f"{p2}: the top card is not-a-shipped-diff, the latest diff {latest[p2]}",
    ])


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


# --- pending (not yet enforced) diffs: docs/pending-amendments/spec.md -------
# Clock-free on purpose: whether a date has passed is the pipeline's question
# (pending.py --check); these pin what must hold of the shipped bytes at any time.

def _pending_diffs():
    out = []
    for p in shipped_diffs():
        doc = json.loads(p.read_text())
        if "pending" in doc:
            out.append((p, doc))
    return out


def test_pending_diffs_carry_no_ai_prose():
    for p, d in _pending_diffs():
        assert "pr_summary" not in d, p.name
        assert not any("annotation" in e for e in d["diffs"]), p.name


def test_pending_diffs_agree_with_their_timeline():
    for p, d in _pending_diffs():
        tl = json.loads((SHIPPED / "timelines" / f"{d['law_id']}.json").read_text())
        by_id = {e["law_revision_id"]: e for e in tl["timeline"]}
        for r in d["pending"]["revisions"]:
            e = by_id.get(r["law_revision_id"])
            assert e is not None, (p.name, r["law_revision_id"])
            assert e["enforcement_date"] == d["date_after"], (p.name, r["law_revision_id"])
            assert e["diff_id"] == p.stem, (p.name, r["law_revision_id"])
            # the page and the timeline must state the same certainty of the date
            assert e.get("enforcement_comment") == r["enforcement_comment"], p.name
        for u in d["pending"]["unenforced_before"]:
            assert u["law_revision_id"] in by_id, (p.name, u["law_revision_id"])
            assert u["enforcement_date"] < d["date_after"], p.name


def test_a_pending_diff_names_its_amending_laws():
    # The page is named by law number, never by a year that may not hold.
    for p, d in _pending_diffs():
        assert d["pending"]["revisions"], p.name
        for r in d["pending"]["revisions"]:
            assert r["amendment_law_num"] or r["amendment_law_title"], p.name
