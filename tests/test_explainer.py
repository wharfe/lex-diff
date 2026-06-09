import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from explainer import select_changes


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
