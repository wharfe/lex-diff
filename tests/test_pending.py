"""pending.py: not-yet-enforced amendments as diffs, and the freshness check.

process_law is pure (fetching is injected, nothing is written), so both the
publishing run and --check go through it; --check compares what it would
publish now against what ships, by content.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pending

TODAY = "2026-10-11"
C = "公布の日から起算して五年を超えない範囲内において政令で定める日"


def _rev(rid, date, status="UnEnforced", comment="", sched=None,
         num="令和五年法律第五十三号", title="整備法"):
    return {"law_revision_id": rid, "amendment_enforcement_date": date,
            "current_revision_status": status, "amendment_enforcement_comment": comment,
            "amendment_scheduled_enforcement_date": sched, "amendment_law_num": num,
            "amendment_law_title": title}


def _article(num, text):
    return {"tag": "Article", "attr": {"Num": num}, "children": [
        {"tag": "ArticleTitle", "attr": {}, "children": [f"第{num}条"]},
        {"tag": "Paragraph", "attr": {"Num": "1"}, "children": [
            {"tag": "ParagraphSentence", "attr": {}, "children": [
                {"tag": "Sentence", "attr": {}, "children": [text]}]}]}]}


def _table():
    return {"tag": "TableStruct", "attr": {}, "children": [
        {"tag": "Table", "attr": {}, "children": ["表"]}]}


def _law(rev_id, *children, table=None):
    main = list(children) + ([table] if table else [])
    return {
        "revision_info": {"law_title": "テスト法", "law_revision_id": rev_id,
                          "amendment_law_title": "整備法",
                          "amendment_enforcement_date": None},
        "law_full_text": {"tag": "Law", "attr": {}, "children": [
            {"tag": "LawBody", "attr": {}, "children": [
                {"tag": "MainProvision", "attr": {}, "children": main}]}]},
    }


def _fetcher(snapshots):
    def fetch(law_id, asof):
        return snapshots[asof]
    return fetch


# --- pending_dates / pending_block / unenforced_before ---------------------

def test_pending_dates_keeps_only_future_unenforced():
    revs = [_rev("a", "2028-06-13"), _rev("b", "2026-04-01", status="CurrentEnforced"),
            _rev("c", TODAY)]  # in force today, not pending
    assert list(pending.pending_dates(revs, TODAY)) == ["2028-06-13"]


def test_same_day_pending_revisions_are_all_listed():
    revs = [_rev("a", "2028-12-23", title="甲法"), _rev("b", "2028-12-23", title="乙法")]
    got = pending.pending_dates(revs, TODAY)["2028-12-23"]
    assert [r["law_revision_id"] for r in got] == ["a", "b"]


def test_unenforced_without_a_date_is_reported_and_the_law_continues():
    # one undated revision must not stop every other pending date of the law
    revs = REVS + [_rev("u", None)]
    snaps = {
        "2027-06-22": _law("cur", _article("1", "現行")),
        "2027-06-23": _law("p1", _article("1", "一次")),
        "2028-06-12": _law("p1", _article("1", "一次")),
        "2028-06-13": _law("p2", _article("1", "二次")),
    }
    r = pending.process_law("L", revs, _fetcher(snaps), TODAY, frozenset())
    assert len(r["published"]) == 2
    assert any("u" in e for e in r["errors"])


def test_pending_block_keeps_the_comment_verbatim_and_blank_as_none():
    b = pending.pending_block(
        [_rev("a", "2028-06-13", comment=C, sched="2028-06-13"), _rev("b", "2028-06-13")],
        TODAY, [])
    assert b["revisions"][0]["enforcement_comment"] == C
    assert b["revisions"][0]["scheduled_enforcement_date"] == "2028-06-13"
    assert b["revisions"][1]["enforcement_comment"] is None
    assert b["generated_on"] == TODAY


def test_unenforced_before_lists_what_the_before_text_already_contains():
    revs = [_rev("x", "2026-04-01", status="CurrentEnforced"),
            _rev("a", "2027-06-23", comment=C, sched="2027-06-23"),
            _rev("b", "2028-06-13"), _rev("c", "2029-01-01")]
    got = pending.unenforced_before(revs, "2028-06-13")
    assert [r["law_revision_id"] for r in got] == ["a"]
    assert got[0]["enforcement_comment"] == C


# --- process_law ------------------------------------------------------------

REVS = [_rev("cur", "2026-04-01", status="CurrentEnforced"),
        _rev("p1", "2027-06-23"), _rev("p2", "2028-06-13")]


def test_process_law_builds_one_pending_doc_per_date():
    snaps = {
        "2027-06-22": _law("cur", _article("1", "現行")),
        "2027-06-23": _law("p1", _article("1", "一次")),
        "2028-06-12": _law("p1", _article("1", "一次")),
        "2028-06-13": _law("p2", _article("1", "二次")),
    }
    r = pending.process_law("L", REVS, _fetcher(snaps), TODAY, frozenset())
    assert r["errors"] == []
    assert r["published"] == ["L_2027-06-22_2027-06-23", "L_2028-06-12_2028-06-13"]
    doc = r["docs"]["L_2028-06-12_2028-06-13"]
    assert doc["pending"]["revisions"][0]["law_revision_id"] == "p2"
    assert [u["law_revision_id"] for u in doc["pending"]["unenforced_before"]] == ["p1"]
    assert "pr_summary" not in doc
    assert set(r["raws"]) == {"L_2027-06-22.json", "L_2027-06-23.json",
                              "L_2028-06-12.json", "L_2028-06-13.json"}


def test_tables_changed_is_withheld_and_run_continues():
    snaps = {
        "2027-06-22": _law("cur", _article("1", "現行")),
        "2027-06-23": _law("p1", _article("1", "現行"), table=_table()),
        "2028-06-12": _law("p1", _article("1", "現行"), table=_table()),
        "2028-06-13": _law("p2", _article("1", "二次"), table=_table()),
    }
    r = pending.process_law("L", REVS, _fetcher(snaps), TODAY, frozenset())
    assert r["withheld"] == ["L_2027-06-22_2027-06-23"]
    assert r["published"] == ["L_2028-06-12_2028-06-13"]
    assert r["errors"] == []


def test_a_shipped_pair_that_became_empty_is_an_error():
    revs = [_rev("cur", "2026-04-01", status="CurrentEnforced"), _rev("p1", "2027-06-23")]
    snaps = {"2027-06-22": _law("cur", _article("1", "同")),
             "2027-06-23": _law("p1", _article("1", "同"))}
    r = pending.process_law("L", revs, _fetcher(snaps), TODAY,
                            frozenset({"L_2027-06-22_2027-06-23"}))
    assert r["published"] == []
    assert any("L_2027-06-22_2027-06-23" in e for e in r["errors"])


def test_a_wrong_before_revision_is_an_error():
    # e-Gov returned the current text for D-1 although p1 should apply first
    snaps = {
        "2027-06-22": _law("cur", _article("1", "現行")),
        "2027-06-23": _law("p1", _article("1", "一次")),
        "2028-06-12": _law("cur", _article("1", "現行")),
        "2028-06-13": _law("p2", _article("1", "二次")),
    }
    r = pending.process_law("L", REVS, _fetcher(snaps), TODAY, frozenset())
    assert r["published"] == ["L_2027-06-22_2027-06-23"]
    assert any("2028-06-12" in e for e in r["errors"])


def test_a_wrong_after_revision_is_an_error():
    revs = [_rev("cur", "2026-04-01", status="CurrentEnforced"), _rev("p1", "2027-06-23")]
    snaps = {"2027-06-22": _law("cur", _article("1", "現行")),
             "2027-06-23": _law("cur", _article("1", "一次"))}
    r = pending.process_law("L", revs, _fetcher(snaps), TODAY, frozenset())
    assert r["published"] == [] and r["errors"]


# --- check ------------------------------------------------------------------

def _fresh(docs=None, **kw):
    base = {"docs": docs or {}, "raws": {}, "published": list((docs or {}).keys()),
            "withheld": [], "skipped": [], "errors": []}
    base.update(kw)
    return base


def _doc(text, generated_on=TODAY, **extra):
    d = {"law_id": "L", "diffs": [{"article_num": "1", "lines_after": [text]}],
         "pending": {"generated_on": generated_on, "revisions": [], "unenforced_before": []}}
    d.update(extra)
    return d


def test_check_passes_when_content_is_unchanged():
    shipped = {"L_a_b": _doc("新", generated_on="2026-01-01", proposer={"x": 1})}
    assert pending.check({"L": shipped}, {"L": _fresh({"L_a_b": _doc("新")})}) == []


def test_check_reports_changed_content_under_the_same_id():
    # e-Gov updates a pending revision's text without changing its id (measured)
    shipped = {"L_a_b": _doc("新")}
    probs = pending.check({"L": shipped}, {"L": _fresh({"L_a_b": _doc("改")})})
    assert len(probs) == 1 and "L_a_b" in probs[0]


def test_check_reports_a_shipped_pending_diff_that_is_no_longer_produced():
    # enforced, or its date moved: either way this pair is not pending any more
    probs = pending.check({"L": {"L_a_b": _doc("新")}}, {"L": _fresh({})})
    assert len(probs) == 1 and "L_a_b" in probs[0]


def test_check_reports_an_unshipped_pending_diff():
    probs = pending.check({"L": {}}, {"L": _fresh({"L_c_d": _doc("新")})})
    assert len(probs) == 1 and "L_c_d" in probs[0]


def test_check_reports_processing_errors():
    probs = pending.check({"L": {}}, {"L": _fresh({}, errors=["L: boom"])})
    assert probs == ["L: boom"]


def test_check_does_not_report_a_withheld_pair_that_never_shipped():
    probs = pending.check({"L": {}}, {"L": _fresh({}, withheld=["L_e_f"])})
    assert probs == []


def test_unenforced_before_keeps_an_overdue_unenforced_revision():
    # past its date but e-Gov has not flipped it yet: the D-1 text still has it
    revs = [_rev("o", "2026-10-01"), _rev("b", "2028-06-13")]
    assert [r["law_revision_id"] for r in pending.unenforced_before(revs, "2028-06-13")] == ["o"]


def test_check_does_not_tell_to_remove_what_it_could_not_rebuild():
    probs = pending.check({"L": {"L_a_b": _doc("新")}},
                          {"L": _fresh({}, errors=["L_a_b: fetch failed: timeout"])})
    assert any("fetch failed" in p for p in probs)
    assert not any("remove" in p for p in probs)


def test_check_names_a_status_only_change_as_such():
    old = _doc("新")
    new = _doc("新")
    new["pending"]["unenforced_before"] = [{"law_revision_id": "z"}]
    [p] = pending.check({"L": {"L_a_b": old}}, {"L": _fresh({"L_a_b": new})})
    assert "本文は同じ" in p


def test_stale_shipped_lists_shipped_pending_diffs_not_rebuilt():
    assert pending.stale_shipped({"L_a_b": _doc("新"), "L_c_d": _doc("x")},
                                 _fresh({"L_c_d": _doc("x")})) == ["L_a_b"]


def test_merge_for_write_keeps_the_shipped_proposer():
    old = _doc("新", proposer={"submission_type": "閣法"})
    new = _doc("改")
    assert pending.merge_for_write(old, new)["proposer"] == {"submission_type": "閣法"}
    assert pending.merge_for_write(None, new) is new


def test_a_malformed_response_is_an_error_for_that_pair_only():
    snaps = {
        "2027-06-22": {"unexpected": "shape"},
        "2027-06-23": _law("p1", _article("1", "一次")),
        "2028-06-12": _law("p1", _article("1", "一次")),
        "2028-06-13": _law("p2", _article("1", "二次")),
    }
    r = pending.process_law("L", REVS, _fetcher(snaps), TODAY, frozenset())
    assert r["published"] == ["L_2028-06-12_2028-06-13"]
    assert any("L_2027-06-22_2027-06-23" in e for e in r["errors"])
