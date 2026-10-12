"""build_diff_document: the diff JSON assembled from two snapshots, with no I/O.

diff.main() and pending.py both publish through it, so a pending diff and an
enforced one cannot drift apart in shape.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import diff


def _law(children, rev_id, title="改正法", date="2026-04-01"):
    return {
        "revision_info": {
            "law_title": "テスト法",
            "law_revision_id": rev_id,
            "amendment_law_title": title,
            "amendment_enforcement_date": date,
        },
        "law_full_text": {"tag": "Law", "attr": {}, "children": [
            {"tag": "LawBody", "attr": {}, "children": [
                {"tag": "MainProvision", "attr": {}, "children": children}]}]},
    }


def _article(num, text):
    return {"tag": "Article", "attr": {"Num": num}, "children": [
        {"tag": "ArticleTitle", "attr": {}, "children": [f"第{num}条"]},
        {"tag": "Paragraph", "attr": {"Num": "1"}, "children": [
            {"tag": "ParagraphSentence", "attr": {}, "children": [
                {"tag": "Sentence", "attr": {}, "children": [text]}]}]}]}


REVS = [{"law_revision_id": "X_20260401", "amendment_law_title": "改正法",
         "amendment_enforcement_date": "2026-04-01"}]


def test_build_diff_document_names_the_revision():
    before = _law([_article("1", "旧")], "X_20260331")
    after = _law([_article("1", "新")], "X_20260401")
    doc = diff.build_diff_document("X", "2026-03-31", "2026-04-01", before, after, REVS)
    assert doc["revision_after"]["amendment_law_title"] == "改正法"
    assert [d["article_num"] for d in doc["diffs"]] == ["1"]
    assert doc["stats"]["modified"] == 1
    assert "pending" not in doc


def test_build_diff_document_refuses_an_unlisted_revision():
    before = _law([_article("1", "旧")], "X_20260331")
    after = _law([_article("1", "新")], "X_20260401")
    with pytest.raises(ValueError, match="does not list"):
        diff.build_diff_document("X", "2026-03-31", "2026-04-01", before, after, [])
