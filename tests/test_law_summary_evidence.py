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
from law_summary import build_evidence, load_evidence


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


def test_load_evidence_raises_when_no_snapshot_exists(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_evidence(tmp_path, "129AC0000000089")


def test_load_evidence_uses_the_newest_snapshot(tmp_path):
    for date, caption in (("2020-01-01", "（古い規定）"), ("2024-01-01", "（新しい規定）")):
        tree = node(
            "Law",
            node(
                "LawBody",
                node(
                    "MainProvision",
                    node("Chapter", node("ChapterTitle", text_node("第一章"))),
                    article("1", caption, "本文。"),
                ),
            ),
        )
        (tmp_path / f"999AC0000000001_{date}.json").write_text(
            json.dumps({"law_full_text": tree}, ensure_ascii=False)
        )
    # A law revised twice must be described as it stands now, not as it was.
    evidence = load_evidence(tmp_path, "999AC0000000001")
    assert "（新しい規定）" in evidence
    assert "（古い規定）" not in evidence


def test_load_evidence_ignores_the_revisions_file(tmp_path):
    # data/raw also holds <law_id>_revisions.json, which has no law_full_text.
    (tmp_path / "999AC0000000001_revisions.json").write_text(
        json.dumps({"revisions": []}, ensure_ascii=False)
    )
    with pytest.raises(FileNotFoundError):
        load_evidence(tmp_path, "999AC0000000001")


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


def test_future_dated_snapshot_is_not_used(tmp_path):
    # The pipeline routinely fetches an enforcement date months ahead in order
    # to diff against it, so the newest file on disk is regularly one that has
    # not taken effect. A summary describes the law as it stands.
    _write_snapshot(tmp_path, "999AC0000000001", "2024-01-01", "（現行の規定）")
    _write_snapshot(tmp_path, "999AC0000000001", "2099-01-01", "（未施行の規定）")
    evidence = load_evidence(tmp_path, "999AC0000000001", "2026-09-08")
    assert "（現行の規定）" in evidence
    assert "（未施行の規定）" not in evidence


def test_unreadable_newest_snapshot_does_not_fall_back_to_an_older_one(tmp_path):
    # Falling back looks like success and publishes superseded law as current.
    _write_snapshot(tmp_path, "999AC0000000001", "2020-01-01", "（古い規定）")
    (tmp_path / "999AC0000000001_2024-01-01.json").write_text("{ not json")
    with pytest.raises(ValueError):
        load_evidence(tmp_path, "999AC0000000001", "2026-09-08")


def test_newest_snapshot_without_law_full_text_does_not_fall_back(tmp_path):
    _write_snapshot(tmp_path, "999AC0000000001", "2020-01-01", "（古い規定）")
    (tmp_path / "999AC0000000001_2024-01-01.json").write_text(
        json.dumps({"error": "not found"}, ensure_ascii=False)
    )
    with pytest.raises(ValueError):
        load_evidence(tmp_path, "999AC0000000001", "2026-09-08")


def test_revisions_file_is_excluded_by_name(tmp_path):
    # It sorts after every dated snapshot, so excluding it only incidentally
    # (by having no law_full_text) would make it the newest candidate and turn
    # every run into the fall-back error above.
    _write_snapshot(tmp_path, "999AC0000000001", "2024-01-01", "（現行の規定）")
    (tmp_path / "999AC0000000001_revisions.json").write_text(
        json.dumps({"revisions": []}, ensure_ascii=False)
    )
    assert "（現行の規定）" in load_evidence(tmp_path, "999AC0000000001", "2026-09-08")


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


def test_snapshot_with_a_non_date_suffix_is_ignored(tmp_path):
    # "<law_id>_2025-01-01_copy.json" sorts after the real file and would be
    # picked as newest, its non-date name then compared as if it were a date.
    _write_snapshot(tmp_path, "999AC0000000001", "2024-01-01", "（本物）")
    (tmp_path / "999AC0000000001_2024-01-01_copy.json").write_text("{ not json")
    assert "（本物）" in load_evidence(tmp_path, "999AC0000000001", "2026-09-08")


def test_main_refuses_a_snapshot_that_is_not_todays(monkeypatch, tmp_path):
    # The evidence for "the law as it stands" has to be fetched today. The
    # earlier design compared against <law_id>_revisions.json, whose own
    # freshness nobody guaranteed — a missing or stale list passed silently.
    raw = tmp_path / "raw"; raw.mkdir()
    _write_snapshot(raw, "140AC0000000045", "2020-01-01", "（古い規定）")
    tl = tmp_path / "timelines"; tl.mkdir()
    (tl / "140AC0000000045.json").write_text(json.dumps(
        {"law_title": "刑法", "law_num": "x", "revision_count": 1, "timeline": []},
        ensure_ascii=False))
    called = []
    monkeypatch.setattr(law_summary, "DATA_DIR", tmp_path)
    monkeypatch.setattr(law_summary, "FRONTEND_DIR", tmp_path / "frontend")
    monkeypatch.setattr(law_summary, "load_env", lambda: None)
    monkeypatch.setattr(law_summary, "generate_summary",
                        lambda *a, **k: called.append(1))
    monkeypatch.setattr(sys, "argv", ["law_summary.py", "140AC0000000045"])

    with pytest.raises(SystemExit) as exc:
        law_summary.main()

    assert exc.value.code == 3
    assert called == [], "the model was called with law text that is not today's"
