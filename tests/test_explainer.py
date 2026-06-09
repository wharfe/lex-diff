import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from explainer import select_changes, validate_explainer, normalize_explainer


def test_select_dedupes_by_title_prefers_diff_id():
    timeline = [
        {"enforcement_date": "2024-04-01", "amendment_law_title": "民法等の一部を改正する法律",
         "diff_id": "129_2024"},
        {"enforcement_date": "2026-04-01", "amendment_law_title": "民法等の一部を改正する法律",
         "diff_id": None},
    ]
    result = select_changes(timeline)
    # same title collapses to one, the diff_id-bearing entry wins (grounded)
    assert len(result) == 1
    assert result[0]["grounded"] is True
    assert result[0]["diff_id"] == "129_2024"
    assert result[0]["year"] == "2024"


def test_select_grounded_first_then_date_desc():
    timeline = [
        {"enforcement_date": "2020-01-01", "amendment_law_title": "A法", "diff_id": "d1"},
        {"enforcement_date": "2025-01-01", "amendment_law_title": "B法", "diff_id": None},
        {"enforcement_date": "2023-01-01", "amendment_law_title": "C法", "diff_id": None},
    ]
    result = select_changes(timeline)
    # grounded (A) first, then ungrounded by date desc (B 2025, C 2023)
    assert [c["year"] for c in result] == ["2020", "2025", "2023"]
    assert result[0]["grounded"] is True
    assert result[1]["grounded"] is False


def test_select_caps_at_four_and_skips_empty_title():
    timeline = [{"enforcement_date": f"20{10+i}-01-01",
                 "amendment_law_title": f"法{i}", "diff_id": None} for i in range(6)]
    timeline.append({"enforcement_date": "2030-01-01", "amendment_law_title": "", "diff_id": None})
    result = select_changes(timeline)
    assert len(result) == 4
    assert all(c["year"] for c in result)


VALID_YEARS = {"2024", "2026"}


def _ok_explainer():
    return {
        "intro": "不動産登記法は近年、相続登記の義務化など大きな改正が続いています。マイホームや相続の手続きに直接関わる重要な変更です。",
        "recent_changes": [
            {"year": "2024", "title": "相続登記の義務化", "what": "相続を知った日から3年以内の登記が必須になりました。",
             "why": "所有者不明土地の増加が社会問題化したためです。", "impact": "相続人は期限内の手続きが必要です。", "grounded": True},
            {"year": "2026", "title": "登記手続のデジタル化", "what": "オンラインでの手続きが拡充されました。", "grounded": False},
        ],
        "faq": [{"q": "相続登記はいつから義務？", "a": "2024年4月1日から施行されています。"}],
    }


def test_validate_passes_on_good_explainer():
    assert validate_explainer(_ok_explainer(), VALID_YEARS) == []


def test_validate_flags_ungrounded_with_why():
    bad = _ok_explainer()
    bad["recent_changes"][1]["why"] = "推測の背景"
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("ungrounded" in e for e in errors)


def test_validate_flags_year_not_in_timeline():
    bad = _ok_explainer()
    bad["recent_changes"][0]["year"] = "1999"
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("year" in e for e in errors)


def test_validate_flags_missing_key():
    bad = _ok_explainer()
    del bad["intro"]
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("intro" in e for e in errors)


def test_normalize_reattaches_year_grounded_and_strips_ungrounded():
    selected = [
        {"year": "2024", "source_title": "民法等の一部を改正する法律", "grounded": True},
        {"year": "2026", "source_title": "整理法", "grounded": False},
    ]
    raw = {
        "intro": "  導入文  ",
        "recent_changes": [
            {"title": "相続登記の義務化", "what": "3年以内に登記。", "why": "所有者不明土地対策。", "impact": "過料あり。"},
            {"title": "技術的整理", "what": "条ずれの整理。", "why": "LLMが勝手に書いた背景", "impact": "影響も勝手に"},
        ],
        # faq missing entirely
    }
    result = normalize_explainer(raw, selected)
    assert result["intro"] == "導入文"
    assert result["recent_changes"][0]["grounded"] is True
    assert result["recent_changes"][0]["why"] == "所有者不明土地対策。"
    # ungrounded: why/impact stripped
    assert result["recent_changes"][1]["grounded"] is False
    assert "why" not in result["recent_changes"][1]
    assert "impact" not in result["recent_changes"][1]
    # faq normalized to []
    assert result["faq"] == []


def test_normalize_filters_incomplete_faq():
    selected = [{"year": "2024", "source_title": "X", "grounded": True}]
    raw = {"intro": "x", "recent_changes": [{"title": "t", "what": "w", "why": "y", "impact": "i"}],
           "faq": [{"q": "問", "a": "答"}, {"q": "", "a": "答だけ"}, {"q": "問だけ"}]}
    result = normalize_explainer(raw, selected)
    assert result["faq"] == [{"q": "問", "a": "答"}]


def test_validate_flags_non_dict_items_without_crashing():
    bad = _ok_explainer()
    bad["recent_changes"][0] = "not a dict"
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("recent_changes[0]" in e for e in errors)

    bad2 = _ok_explainer()
    bad2["faq"] = ["not a dict"]
    errors2 = validate_explainer(bad2, VALID_YEARS)
    assert any("faq[0]" in e for e in errors2)


def test_select_dedupes_by_diff_id_across_titles():
    # Two different amendment titles share the SAME diff_id (same snapshot).
    timeline = [
        {"enforcement_date": "2024-04-01", "amendment_law_title": "デジタル改革法", "diff_id": "416_2024"},
        {"enforcement_date": "2024-04-01", "amendment_law_title": "民法等改正", "diff_id": "416_2024"},
        {"enforcement_date": "2026-04-01", "amendment_law_title": "公益信託法", "diff_id": None},
    ]
    result = select_changes(timeline)
    diff_ids = [c["diff_id"] for c in result if c["diff_id"]]
    assert diff_ids == ["416_2024"]  # the shared diff_id appears only once
    # the None-diff ungrounded entry survives
    assert any(c["diff_id"] is None for c in result)


def test_select_does_not_collapse_distinct_none_diff_ids():
    timeline = [
        {"enforcement_date": "2025-01-01", "amendment_law_title": "A法", "diff_id": None},
        {"enforcement_date": "2024-01-01", "amendment_law_title": "B法", "diff_id": None},
    ]
    result = select_changes(timeline)
    assert len(result) == 2  # two None-diff entries are NOT merged


def test_normalize_skips_non_dict_change_items():
    selected = [
        {"year": "2024", "source_title": "X", "grounded": True},
        {"year": "2026", "source_title": "Y", "grounded": False},
    ]
    raw = {"intro": "i", "recent_changes": ["garbage", {"title": "t", "what": "w"}], "faq": "notalist"}
    result = normalize_explainer(raw, selected)
    # non-dict change item is skipped, not crashed on; valid one is kept
    assert all(isinstance(c, dict) for c in result["recent_changes"])
    assert any(c["title"] == "t" for c in result["recent_changes"])
    # non-list faq normalizes to []
    assert result["faq"] == []
