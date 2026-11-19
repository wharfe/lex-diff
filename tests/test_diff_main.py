"""diff.main() run end to end over a minimal fixture (issue #15).

test_shipped_data.py checks that the published `stats` agree with
compute_stats(diffs), but only over JSON that already exists: a producer that
stopped writing `stats` (or wrote stale ones) would stay green until the data
was regenerated. This runs the producer itself — raw snapshots on disk in,
diff JSON on disk out — and checks the `stats` it wrote.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import diff

LAW_ID = "999AC0000000001"
BEFORE = "2026-03-31"
AFTER = "2026-04-01"
AMEND = "令和八年法律第一号"


def _article(num, text):
    return {"tag": "Article", "attr": {"Num": num}, "children": [
        {"tag": "ArticleTitle", "attr": {}, "children": [f"第{num}条"]},
        {"tag": "Paragraph", "attr": {"Num": "1"}, "children": [
            {"tag": "ParagraphSentence", "attr": {}, "children": [
                {"tag": "Sentence", "attr": {}, "children": [text]}]}]}]}


def _snapshot(main_articles, suppl_blocks, rev_id, title, date):
    body = [{"tag": "MainProvision", "attr": {}, "children": main_articles}]
    for amend_num, arts in suppl_blocks:
        body.append({"tag": "SupplProvision", "attr": {"AmendLawNum": amend_num},
                     "children": [{"tag": "SupplProvisionLabel", "attr": {},
                                   "children": ["附　則"]}, *arts]})
    return {
        "revision_info": {
            "law_title": "テスト法",
            "law_revision_id": rev_id,
            "amendment_law_title": title,
            "amendment_enforcement_date": date,
        },
        "law_full_text": {"tag": "Law", "attr": {}, "children": [
            {"tag": "LawBody", "attr": {}, "children": body}]},
    }


def _write_raw(raw_dir):
    """本則: 第1条 modified, 第2条 deleted, 第3条 added; 附則: one block added.

    One of each type, so a count that swaps two types or folds 附則 into 本則
    cannot pass by coincidence.
    """
    before = _snapshot(
        [_article("1", "旧規定"), _article("2", "廃止される規定")],
        [],
        f"{LAW_ID}_20260331", "前の改正法", "2025-04-01",
    )
    after = _snapshot(
        [_article("1", "新規定"), _article("3", "追加された規定")],
        [(AMEND, [_article("1", "この法律は、令和八年四月一日から施行する。")])],
        f"{LAW_ID}_20260401", "テスト法の一部を改正する法律", AFTER,
    )
    revisions = {"revisions": [
        {"law_revision_id": f"{LAW_ID}_20260401",
         "amendment_law_title": "テスト法の一部を改正する法律",
         "amendment_enforcement_date": AFTER},
        {"law_revision_id": f"{LAW_ID}_20260331",
         "amendment_law_title": "前の改正法",
         "amendment_enforcement_date": "2025-04-01"},
    ]}
    raw_dir.mkdir(parents=True)
    (raw_dir / f"{LAW_ID}_{BEFORE}.json").write_text(json.dumps(before, ensure_ascii=False))
    (raw_dir / f"{LAW_ID}_{AFTER}.json").write_text(json.dumps(after, ensure_ascii=False))
    (raw_dir / f"{LAW_ID}_revisions.json").write_text(json.dumps(revisions, ensure_ascii=False))


def _run_main(monkeypatch, tmp_path):
    raw_dir = tmp_path / "raw"
    diff_dir = tmp_path / "diffs"
    _write_raw(raw_dir)
    monkeypatch.setattr(diff, "DATA_DIR", tmp_path)
    monkeypatch.setattr(diff, "RAW_DIR", raw_dir)
    monkeypatch.setattr(diff, "DIFF_DIR", diff_dir)
    # main() only reads SHIPPED_DIR on the no-changes path, but point it away
    # from frontend/public/data so no run of this test can touch shipped data.
    monkeypatch.setattr(diff, "SHIPPED_DIR", tmp_path / "shipped")
    monkeypatch.setattr(sys, "argv", ["diff.py", LAW_ID, BEFORE, AFTER])
    diff.main()
    return diff_dir / f"{LAW_ID}_{BEFORE}_{AFTER}.json"


def test_main_writes_main_only_stats(monkeypatch, tmp_path):
    out_path = _run_main(monkeypatch, tmp_path)
    doc = json.loads(out_path.read_text())

    # The literal values, not just compute_stats(doc["diffs"]): agreeing with
    # the diffs it shipped beside would also pass if both were wrong together.
    assert doc["stats"] == {
        "added": 1,
        "modified": 1,
        "deleted": 1,
        "main": 3,
        "suppl": 1,
    }
    assert doc["stats"] == diff.compute_stats(doc["diffs"])


def test_main_writes_the_diffs_the_stats_count(monkeypatch, tmp_path):
    out_path = _run_main(monkeypatch, tmp_path)
    doc = json.loads(out_path.read_text())

    by_key = {d["article_num"]: (d["type"], d.get("is_suppl", False)) for d in doc["diffs"]}
    assert by_key == {
        "1": ("modified", False),
        "2": ("deleted", False),
        "3": ("added", False),
        diff.suppl_key(AMEND, "1"): ("added", True),
    }
    assert doc["law_id"] == LAW_ID
    assert (doc["date_before"], doc["date_after"]) == (BEFORE, AFTER)
