import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from explainer import (
    MAX_CHANGES,
    normalize_explainer,
    select_changes,
    validate_explainer,
    validate_explainer_shape,
)

# An item is one enforced diff whose 本則 changed (docs/issue-35/spec.md). The
# unit used to be one amending law, matched by title: distinct laws sharing a
# title were folded together, and a 附則-only stage of a law whose 本則 was
# still pending went to the model as "本則は変わらない" (公益通報者保護法).


def _diff(main=3, pending=False, titles=None, pr=True):
    d = {
        "stats": {"main": main},
        "revision_after": {"amendment_law_title": (titles or ["A法"])[0]},
    }
    if titles and len(titles) > 1:
        d["revision_after"]["amendment_law_titles"] = titles
    if pr:
        d["pr_summary"] = {"title": "t", "summary": "s", "background": "b", "impact": "i"}
    if pending:
        d["pending"] = {"generated_on": "2026-10-12"}
    return d


def _entry(date, diff_id, title="A法", **extra):
    return {"enforcement_date": date, "amendment_law_title": title, "diff_id": diff_id, **extra}


def _select(timeline, diffs, today="2026-10-18", pending_ids=frozenset(), tables=frozenset()):
    def load(diff_id):
        return diffs.get(diff_id)
    return select_changes(timeline, today, pending_ids, load, lambda d: d in tables)


def test_distinct_laws_with_one_title_are_separate_items():
    # 公益通報者保護法: 令和2年 and 令和7年 amendments share their title.
    timeline = [_entry("2025-06-11", "d2025", "公益通報者保護法の一部を改正する法律"),
                _entry("2022-06-01", "d2022", "公益通報者保護法の一部を改正する法律")]
    result = _select(timeline, {"d2025": _diff(), "d2022": _diff()})
    assert [c["diff_id"] for c in result] == ["d2025", "d2022"]


def test_a_diff_whose_main_text_did_not_change_is_not_an_item():
    timeline = [_entry("2026-05-21", "suppl_only"), _entry("2025-06-12", "real")]
    result = _select(timeline, {"suppl_only": _diff(main=0), "real": _diff(main=11)})
    assert [c["diff_id"] for c in result] == ["real"]


def test_pending_entries_and_pending_diffs_never_reach_the_model():
    timeline = [
        _entry("2026-12-01", "future"),                       # date after today
        _entry("2026-11-26", "commented", enforcement_comment="政令で定める日"),
        _entry("2026-10-01", "overdue"),                      # pending diff past its date
        _entry("2026-07-17", "flagged"),                      # carries a pending block
        _entry("2026-06-01", "ok"),
    ]
    diffs = {k: _diff() for k in ("future", "commented", "overdue", "ok")}
    diffs["flagged"] = _diff(pending=True)
    result = _select(timeline, diffs, pending_ids=frozenset({"overdue"}))
    assert [c["diff_id"] for c in result] == ["ok"]


def test_a_diff_whose_tables_changed_is_not_an_item():
    # Shipped before diff.tables_changed existed (道交法 2026-04-01, 個情 2025-04-01).
    timeline = [_entry("2026-04-01", "tab"), _entry("2024-11-01", "ok")]
    result = _select(timeline, {"tab": _diff(), "ok": _diff()}, tables=frozenset({"tab"}))
    assert [c["diff_id"] for c in result] == ["ok"]


def test_a_shared_diff_is_one_item_named_by_the_diff():
    timeline = [_entry("2025-06-01", "d", "A法"), _entry("2025-06-01", "d", "B法")]
    [c] = _select(timeline, {"d": _diff(titles=["A法", "B法"])})
    assert c["source_title"] == "A法／B法" and c["multi_law"] is True


def test_newest_first_capped():
    timeline = [_entry(f"20{10 + i}-01-01", f"d{i}") for i in range(6)]
    result = _select(timeline, {f"d{i}": _diff() for i in range(6)})
    assert [c["diff_id"] for c in result] == ["d5", "d4", "d3", "d2"][:MAX_CHANGES]
    assert result[0]["enforcement_date"] == "2015-01-01" and result[0]["year"] == "2015"


def test_entries_without_a_diff_are_not_items():
    timeline = [_entry("2025-01-01", None), _entry("2024-01-01", "d")]
    assert [c["diff_id"] for c in _select(timeline, {"d": _diff()})] == ["d"]


def test_an_unreadable_diff_stops_the_run():
    with pytest.raises(ValueError):
        _select([_entry("2025-01-01", "missing")], {})


def test_a_diff_without_pr_summary_stops_the_run():
    with pytest.raises(ValueError):
        _select([_entry("2025-01-01", "d")], {"d": _diff(pr=False)})


def test_same_day_names_come_only_from_entries_of_that_diff():
    # An old diff names one law; the timeline's entries for the same diff_id
    # fill in the rest. A pending entry on the same date is not one of them.
    timeline = [_entry("2025-06-01", "d", "A法"), _entry("2025-06-01", "d", "B法"),
                _entry("2025-06-01", None, "未施行法")]
    [c] = _select(timeline, {"d": _diff(titles=["A法"])})
    assert c["source_title"] == "A法／B法"


# --- normalize / validate ---

SELECTED = [
    {"year": "2026", "enforcement_date": "2026-04-01", "diff_id": "d1", "source_title": "X"},
    {"year": "2024", "enforcement_date": "2024-04-01", "diff_id": "d2", "source_title": "Y"},
]


def _raw():
    return {
        "recent_changes": [
            {"title": "登記のオンライン化", "what": "オンラインでの手続きが広がりました。",
             "why": "手続きの負担を減らすためです。", "impact": "窓口に行かずに済む場面が増えます。"},
            {"title": "相続登記の義務化", "what": "相続で不動産を取得したら登記が必要になりました。"},
        ],
        # A model that still writes these gets them dropped, not shipped.
        "intro": "制度自体は大きく変わっていません。", "faq": [{"q": "q", "a": "a"}],
    }


def _ok():
    return normalize_explainer(_raw(), SELECTED, "2026-10-18")


def test_normalize_attaches_the_deterministic_facts():
    e = _ok()
    assert e["generated_on"] == "2026-10-18"
    assert [(c["diff_id"], c["year"], c["enforcement_date"]) for c in e["recent_changes"]] == [
        ("d1", "2026", "2026-04-01"), ("d2", "2024", "2024-04-01")]
    assert all(c["grounded"] is True for c in e["recent_changes"])
    assert validate_explainer(e, SELECTED, _raw()) == []


def test_a_dropped_item_fails_instead_of_shifting_the_facts():
    raw = _raw()
    raw["recent_changes"] = raw["recent_changes"][1:]
    e = normalize_explainer(raw, SELECTED, "2026-10-18")
    assert any("count" in err for err in validate_explainer(e, SELECTED, raw))


def test_normalize_keeps_only_the_items():
    # intro and faq generalised past the items given (#35); the page writes
    # its own intro.
    e = _ok()
    assert set(e) == {"generated_on", "recent_changes"}
    assert "why" not in e["recent_changes"][1]


@pytest.mark.parametrize("text", [
    "2027年に施行される予定です。",
    "改正の効果が見込まれます。",
    "令和9年から新しい制度が始まります。",
    "令和九年四月一日から変わります。",
    "２０２８年から変わります。",       # full-width, caught after NFKC
    "令和１０年に見直します。",
    # code-review Gate3: same year but after generated_on, a bracketed year,
    # and a kanji 西暦 all passed.
    "2026年12月1日から事業者に体制整備が義務付けられます。",
    "2027（令和9）年から変わります。",
    "二〇二七年から変わります。",
])
def test_future_claims_are_rejected(text):
    e = _ok()
    e["recent_changes"][0]["impact"] = text
    assert validate_explainer_shape(e), text


@pytest.mark.parametrize("text", [
    "2024年4月1日から施行されています。",
    "令和8年5月から変わりました。",
    "今後の手続きはオンラインで行えます。",
    "2026年10月1日から施行されています。",
    "2025（令和7）年に改正されました。",
])
def test_statements_about_the_past_or_present_pass(text):
    e = _ok()
    e["recent_changes"][0]["impact"] = text
    assert validate_explainer_shape(e) == [], text


def test_shape_requires_the_recorded_facts():
    for drop in ("generated_on",):
        e = _ok()
        del e[drop]
        assert validate_explainer_shape(e)
    e = _ok()
    del e["recent_changes"][0]["diff_id"]
    assert validate_explainer_shape(e)
    e = _ok()
    e["recent_changes"][1]["diff_id"] = "d1"
    assert any("duplicate" in err for err in validate_explainer_shape(e))


def test_shape_checks_lengths_and_counts():
    e = _ok()
    e["recent_changes"][0]["what"] = "長" * 121
    assert validate_explainer_shape(e)
    e = _ok()
    e["recent_changes"] = e["recent_changes"] * 3
    assert validate_explainer_shape(e)
    e = _ok()
    e["recent_changes"][0] = "not a dict"
    assert any("recent_changes[0]" in err for err in validate_explainer_shape(e))


def test_an_extra_model_item_fails_instead_of_being_cut():
    # zip() would cut it off and the count would then agree (codex, Gate3).
    raw = _raw()
    raw["recent_changes"].insert(0, {"title": "余分", "what": "選んでいない変更。"})
    e = normalize_explainer(raw, SELECTED, "2026-10-18")
    assert any("count" in err for err in validate_explainer(e, SELECTED, raw))


def test_a_missing_model_item_fails():
    raw = _raw()
    raw["recent_changes"] = raw["recent_changes"][:1]
    e = normalize_explainer(raw, SELECTED, "2026-10-18")
    assert any("count" in err for err in validate_explainer(e, SELECTED, raw))


def test_a_fine_must_keep_its_condition_when_the_evidence_has_one():
    # 不動産登記法 第164条: 「正当な理由がないのに…怠ったときは…過料」. The
    # regenerated text said 「怠ると過料の対象」 (codex, Gate3) — the same error
    # CLAUDE.md records for law-seo.ts.
    selected = [dict(SELECTED[0], pr_summary={"summary": "正当な理由がないのに申請を怠ると5万円以下の過料。"}),
                SELECTED[1]]
    raw = _raw()
    raw["recent_changes"][0]["impact"] = "申請を怠ると過料の対象になります。"
    e = normalize_explainer(raw, selected, "2026-10-18")
    assert any("正当な理由" in err for err in validate_explainer(e, selected, raw))
    raw["recent_changes"][0]["impact"] = "正当な理由なく申請を怠ると過料の対象になります。"
    e = normalize_explainer(raw, selected, "2026-10-18")
    assert validate_explainer(e, selected, raw) == []


def test_a_law_with_no_item_loses_its_explainer(tmp_path, monkeypatch):
    # Spec invariant 6: nothing to write from → no explainer, not a stale one.
    import json
    import explainer as ex
    (tmp_path / "timelines").mkdir()
    path = tmp_path / "timelines" / "L.json"
    path.write_text(json.dumps({"law_title": "X法", "timeline": [],
                                "explainer": {"intro": "古い"}}))
    monkeypatch.setattr(ex, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ex, "FRONTEND_DIR", tmp_path / "frontend")
    monkeypatch.setattr(ex, "load_env", lambda: None)
    monkeypatch.setattr(sys, "argv", ["explainer.py", "L"])
    ex.main()
    assert "explainer" not in json.loads(path.read_text())


def test_each_sentence_naming_a_fine_keeps_its_condition():
    # Per field: 「正当な理由」 in what does not excuse 「怠ると過料」 in impact.
    selected = [dict(SELECTED[0], pr_summary={"summary": "正当な理由がないのに申請を怠ると過料。"}),
                SELECTED[1]]
    raw = _raw()
    raw["recent_changes"][0]["what"] = "正当な理由なく怠ると過料の対象になります。"
    raw["recent_changes"][0]["impact"] = "申請を怠ると過料が科される可能性があります。"
    e = normalize_explainer(raw, selected, "2026-10-18")
    assert any("正当な理由" in err for err in validate_explainer(e, selected, raw))
