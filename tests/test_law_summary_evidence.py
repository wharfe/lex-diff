"""law_summary.py must write from the law's own text, not from memory.

The script used to hand the model nothing but a law's name, number, category
and revision count — every word of the answer came out of the model's memory,
and the only guard was a ban on one pair of abolished penalty names (#16).
These tests pin the evidence path: what goes into the prompt, that it is never
empty, and that a keyword with no basis in the law text cannot be saved.

The fixtures are synthetic trees rather than real snapshots: data/raw/ is
gitignored, so a test reading it would pass locally and fail in CI.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import law_summary
from law_summary import build_evidence, fetch_evidence


def node(tag, *children, **attr):
    return {"tag": tag, "attr": attr, "children": list(children)}


def text_node(s):
    return s


def article(num, caption, body):
    return node(
        "Article",
        node("ArticleCaption", text_node(caption)),
        node("ArticleTitle", text_node(f"第{num}条")),
        node("Paragraph", node("ParagraphSentence", node("Sentence", text_node(body)))),
        Num=num,
    )


def law_tree():
    """A two-chapter law with three articles."""
    return node(
        "Law",
        node(
            "LawBody",
            node(
                "MainProvision",
                node(
                    "Chapter",
                    node("ChapterTitle", text_node("第一章　総則")),
                    article("1", "（目的）", "この法律は、猫の福祉の増進を目的とする。"),
                    article("2", "（定義）", "この法律において「猫」とは、家猫をいう。"),
                ),
                node(
                    "Chapter",
                    node("ChapterTitle", text_node("第二章　給餌")),
                    article("3", "（給餌の義務）", "飼い主は、猫に餌を与えなければならない。"),
                ),
            ),
        ),
    )


def test_evidence_contains_the_table_of_contents():
    evidence = build_evidence(law_tree())
    assert "第一章　総則" in evidence
    assert "第二章　給餌" in evidence


def test_evidence_contains_every_article_caption():
    # The captions are, in effect, the list of everything the law covers —
    # the densest basis available for the description.
    evidence = build_evidence(law_tree())
    for caption in ("（目的）", "（定義）", "（給餌の義務）"):
        assert caption in evidence


def test_evidence_contains_article_one_in_full():
    # Article 1 is the purpose / scope clause, which is the direct basis for
    # the summary's `scope` field.
    evidence = build_evidence(law_tree())
    assert "猫の福祉の増進を目的とする" in evidence


def test_evidence_does_not_contain_later_article_bodies():
    # Only article 1 is included in full; the rest contribute their captions.
    # Otherwise 民法 would put 226,000 characters into the prompt.
    evidence = build_evidence(law_tree())
    assert "餌を与えなければならない" not in evidence


def test_empty_tree_raises_rather_than_returning_empty_evidence():
    # Never call the model with an empty evidence list — the failure that let
    # annotate.py write from memory (CLAUDE.md).
    with pytest.raises(ValueError):
        build_evidence(node("Law", node("LawBody", node("MainProvision"))))


# --- what Gate3 found ---------------------------------------------------------
#
# Each test below pins one finding from the review of this change. They are
# grouped here rather than merged above because the failures they describe all
# survived the first round of tests: every one of them looked like working code.

def suppl_tree():
    """A law with a 附則 block and a TOC, like the real e-Gov trees."""
    return node(
        "Law",
        node(
            "LawBody",
            node(  # the law's own table of contents — repeats the body headings
                "TOC",
                node("TOCChapter", node("ChapterTitle", text_node("第一章　総則"))),
            ),
            node(
                "MainProvision",
                node(
                    "Chapter",
                    node("ChapterTitle", text_node("第一章　総則")),
                    article("1", "（目的）", "この法律は、猫の福祉の増進を目的とする。"),
                ),
            ),
            node(
                "SupplProvision",
                node("SupplProvisionLabel", text_node("附則")),
                article("1", "（施行期日）", "この法律は、公布の日から施行する。"),
            ),
        ),
    )


def test_table_of_contents_is_not_printed_twice():
    # The e-Gov tree carries a TOC element repeating every body heading, so
    # collecting both sent the whole outline twice (民法: 364 lines, 197 of
    # them duplicates).
    evidence = build_evidence(suppl_tree())
    assert evidence.count("第一章　総則") == 1


def test_supplementary_provisions_are_excluded():
    # 附則 is a different axis from the main text and says nothing about what
    # the law is for. This is the largest self-made decision in the evidence
    # design and had no test at all.
    evidence = build_evidence(suppl_tree())
    assert "（施行期日）" not in evidence
    assert "（目的）" in evidence


def test_blank_headings_do_not_count_as_evidence():
    # A heading node whose text is empty makes the list truthy while
    # contributing nothing: testing the lists instead of the assembled text
    # sent the model "## 目次" alone and called it evidence.
    blank = node(
        "Law",
        node("LawBody", node("MainProvision", node(
            "Chapter", node("ChapterTitle", text_node("   "))))),
    )
    with pytest.raises(ValueError):
        build_evidence(blank)


def test_first_article_is_not_labelled_第一条_when_it_is_not():
    # articles[0] is only the first in document order. A law whose 第一条 was
    # 削除 and dropped from the tree would have its 第一条の二 handed over under
    # a label asserting otherwise — and the prompt tells the model this is
    # where `scope` comes from.
    tree = node(
        "Law",
        node("LawBody", node("MainProvision", node(
            "Chapter",
            node("ChapterTitle", text_node("第一章")),
            article("1_2", "（定義）", "この法律において「猫」とは、家猫をいう。")))),
    )
    evidence = build_evidence(tree)
    assert "## 第一条（全文）" not in evidence
    assert "1_2" in evidence
    # The label alone is not enough: the design leans on article 1 being the
    # purpose clause, and the prompt says so. Without this note the model reads
    # a definition clause as if it stated the scope.
    assert "第一条が無い" in evidence
    assert "断定せず" in evidence


# --- choosing which snapshot is "the law as it stands" -------------------------

def _write_snapshot(raw_dir, law_id, date, caption):
    tree = node(
        "Law",
        node("LawBody", node("MainProvision", node(
            "Chapter",
            node("ChapterTitle", text_node("第一章")),
            article("1", caption, "本文。")))),
    )
    (raw_dir / f"{law_id}_{date}.json").write_text(
        json.dumps({"law_full_text": tree}, ensure_ascii=False)
    )


def test_article_with_only_a_title_is_not_evidence():
    # extract_text on such an Article yields "第一条" — a label, not text. The
    # emptiness check has to be structural, not a string length.
    tree = node(
        "Law",
        node("LawBody", node("MainProvision", node(
            "Chapter",
            node("ChapterTitle", text_node("   ")),
            node("Article", node("ArticleTitle", text_node("第一条")), Num="1")))),
    )
    with pytest.raises(ValueError):
        build_evidence(tree)




# --- the evidence is fetched, not found ---------------------------------------
#
# Two rounds of Gate3 tried to decide from disk whether the law text was
# current, and both failed for the same reason: nothing stored on disk says
# when it was obtained. asof is the point in time being asked about, not the
# moment of asking — 129AC0000000089_2026-04-01.json was written on 2026-03-26.

def test_fetch_evidence_uses_what_the_api_just_returned(monkeypatch, tmp_path):
    doc = {"law_full_text": node(
        "Law", node("MainProvision", node(
            "Chapter",
            node("ChapterTitle", text_node("第一章　総則")),
            article("1", "（目的）", "この法律は、猫の福祉の増進を目的とする。"))))}
    monkeypatch.setattr(law_summary, "fetch_law_data", lambda *a, **k: doc)

    evidence = law_summary.fetch_evidence(tmp_path, "999AC0000000001", "2026-09-09")

    assert "（目的）" in evidence
    # and it is kept, so the next diff run has it
    assert (tmp_path / "999AC0000000001_2026-09-09.json").exists()


def test_fetch_evidence_refuses_a_response_without_law_text(monkeypatch, tmp_path):
    # A failed fetch must not fall back to an older file on disk — an older
    # file is exactly what caused this.
    monkeypatch.setattr(law_summary, "fetch_law_data", lambda *a, **k: {"error": "not found"})
    with pytest.raises(ValueError):
        law_summary.fetch_evidence(tmp_path, "999AC0000000001", "2026-09-09")


def test_article_whose_sentence_is_empty_is_not_evidence():
    # A present-but-empty <Sentence/> is what a truncated API response looks
    # like; checking for the tag alone let "第一条" through as article text.
    tree = node(
        "Law",
        node("MainProvision", node(
            "Chapter",
            node("ChapterTitle", text_node("   ")),
            node("Article",
                 node("ArticleTitle", text_node("第一条")),
                 node("Paragraph", node("ParagraphSentence", node("Sentence"))),
                 Num="1"))),
    )
    with pytest.raises(ValueError):
        build_evidence(tree)


def test_headings_do_not_excuse_a_missing_article_body():
    # The reviewer's exact case: chapter heading + article caption + an empty
    # <Sentence/>. The earlier check let this through because the headings
    # alone made the evidence non-empty — while the prompt still told the model
    # the evidence contained article 1, and `scope` had nothing to stand on.
    tree = node(
        "Law",
        node("MainProvision", node(
            "Chapter",
            node("ChapterTitle", text_node("第一章　総則")),
            node("Article",
                 node("ArticleCaption", text_node("（目的）")),
                 node("ArticleTitle", text_node("第一条")),
                 node("Paragraph", node("ParagraphSentence", node("Sentence"))),
                 Num="1"))),
    )
    with pytest.raises(ValueError):
        build_evidence(tree)


def test_a_bad_response_does_not_destroy_the_existing_snapshot(monkeypatch, tmp_path):
    # data/raw is shared with the diff pipeline (diff.py reads these files), so
    # a failed summary must not take a good snapshot down with it.
    path = tmp_path / "999AC0000000001_2026-09-09.json"
    good = json.dumps({"law_full_text": {"tag": "Law", "attr": {}, "children": []},
                       "marker": "the good one"}, ensure_ascii=False)
    path.write_text(good)

    # truthy law_full_text, but nothing build_evidence can use
    monkeypatch.setattr(law_summary, "fetch_law_data",
                        lambda *a, **k: {"law_full_text": node("Law", node("MainProvision"))})
    with pytest.raises(ValueError):
        law_summary.fetch_evidence(tmp_path, "999AC0000000001", "2026-09-09")

    assert path.read_text() == good, "the existing snapshot was overwritten"
    assert not list(tmp_path.glob("*.tmp")), "a temp file was left behind"
