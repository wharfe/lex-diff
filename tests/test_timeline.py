import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from timeline import carry_over


def _rebuilt():
    # What build_timeline produces from the revisions alone (#23).
    return {
        "law_id": "X",
        "timeline": [
            {"law_revision_id": "new", "diff_id": "X_2026-06-23_2026-06-24"},
            {"law_revision_id": "old", "diff_id": "X_2024-03-31_2024-04-01"},
        ],
    }


def _previous():
    return {
        "law_id": "X",
        "summary": {"overview": "o"},
        "category": "民事",
        "contributors": [{"name": "n"}],
        "explainer": {"intro": "i"},
        "timeline": [
            {"law_revision_id": "old", "diff_id": None,
             "proposer": {"submission_type": "閣法"}},
        ],
    }


def test_fields_added_after_the_timeline_was_built_survive_a_rebuild():
    # law_summary/explainer/enrich write these into the timeline afterwards;
    # rebuilding from the revisions alone used to drop every one of them.
    out = carry_over(_rebuilt(), _previous())
    for key in ("summary", "category", "contributors", "explainer"):
        assert out[key] == _previous()[key]


def test_an_entry_keeps_its_proposer_matched_by_revision_id():
    out = carry_over(_rebuilt(), _previous())
    by_id = {e["law_revision_id"]: e for e in out["timeline"]}
    assert by_id["old"]["proposer"] == {"submission_type": "閣法"}
    assert "proposer" not in by_id["new"]


def test_the_rebuild_still_decides_diff_id():
    # diff_id is computed from the shipped diffs; the previous file must not win.
    out = carry_over(_rebuilt(), _previous())
    by_id = {e["law_revision_id"]: e for e in out["timeline"]}
    assert by_id["old"]["diff_id"] == "X_2024-03-31_2024-04-01"


def test_no_previous_timeline_leaves_the_rebuild_as_is():
    assert carry_over(_rebuilt(), None) == _rebuilt()
