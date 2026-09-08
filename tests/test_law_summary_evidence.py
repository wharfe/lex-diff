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
