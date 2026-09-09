"""Integration-level guards on what actually ships.

The other test files check the pure functions, which proves the helpers are
right and not that the published data agrees with them. These read
`frontend/public/data/` — the bytes readers actually get — and fail when it
drifts from what the current code would produce.

What they do NOT cover: the producer wiring. Deleting the `compute_stats(diffs)`
call in `diff.py` leaves these green, because the shipped JSON is only rewritten
when the pipeline runs. Pinning that needs a fixture-driven run of `diff.main()`
(issue #15). The `law_summary.main()` path is covered, in
test_law_summary_validation.py.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from diff import compute_stats
from law_summary import validate_summary_shape

SHIPPED = Path(__file__).parent.parent / "frontend" / "public" / "data"


def shipped_diffs():
    return sorted(p for p in SHIPPED.glob("*_*-*-*_*-*-*.json"))


def shipped_timelines():
    return sorted((SHIPPED / "timelines").glob("*.json"))


def test_shipped_diff_files_are_present():
    # A glob that quietly matches nothing would make every test below vacuous.
    assert len(shipped_diffs()) >= 16


def test_shipped_timeline_files_are_present():
    assert len(shipped_timelines()) >= 12


@pytest.mark.parametrize("path", shipped_diffs(), ids=lambda p: p.name)
def test_shipped_stats_match_compute_stats(path):
    data = json.loads(path.read_text())
    assert data["stats"] == compute_stats(data["diffs"]), (
        f"{path.name}: stats disagree with compute_stats — regenerate or migrate it"
    )


@pytest.mark.parametrize("path", shipped_timelines(), ids=lambda p: p.name)
def test_shipped_law_summaries_are_valid(path):
    summary = json.loads(path.read_text()).get("summary")
    # Every shipped law must have one. This used to skip when summary was None,
    # because four laws (民法・道路交通法・労働基準法・著作権法 — the biggest ones)
    # had never had law_summary.py run over them at all and shipped a /law page
    # with no overview block, issue #14. Closing that issue means the gap
    # cannot reopen silently the next time a law is added.
    assert summary is not None, f"{path.name}: no summary — run law_summary.py"
    assert validate_summary_shape(summary) == [], f"{path.name}: {validate_summary_shape(summary)}"
