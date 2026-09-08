import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from diff import compute_stats


def entry(type_, is_suppl=False):
    return {"type": type_, "is_suppl": is_suppl}


def test_main_counts_exclude_suppl():
    stats = compute_stats(
        [
            entry("modified"),
            entry("added"),
            entry("modified", is_suppl=True),
            entry("deleted", is_suppl=True),
        ]
    )
    assert stats["added"] == 1
    assert stats["modified"] == 1
    assert stats["deleted"] == 0
    assert stats["main"] == 2


def test_suppl_only_amendment_reports_zero_main():
    # 労働基準法 2024: the amendment touched 附則 only. The old stats said
    # "2 modified" here, which is what made the published JSON disagree with the
    # site (frontend/lib/data.ts mainChangeCounts).
    stats = compute_stats([entry("modified", is_suppl=True), entry("added", is_suppl=True)])
    assert (stats["added"], stats["modified"], stats["deleted"]) == (0, 0, 0)
    assert stats["main"] == 0
    assert stats["suppl"] == 2


def test_missing_is_suppl_key_counts_as_main():
    stats = compute_stats([{"type": "added"}])
    assert stats["added"] == 1
    assert stats["main"] == 1
    assert stats["suppl"] == 0


def test_empty_diff_is_all_zero():
    assert compute_stats([]) == {
        "added": 0,
        "modified": 0,
        "deleted": 0,
        "main": 0,
        "suppl": 0,
    }


def test_a_deleted_suppl_article_never_lands_in_the_main_counts():
    stats = compute_stats([entry("deleted", is_suppl=True)])
    assert stats["deleted"] == 0
    assert stats["main"] == 0
    assert stats["suppl"] == 1
