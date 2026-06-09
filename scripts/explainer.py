"""Generate a plain-language 'recent amendments' explainer for a law using Claude AI.

Usage:
    python scripts/explainer.py <law_id>

Example:
    python scripts/explainer.py 416AC0000000123
"""

import sys
import json
import os
from pathlib import Path

MODEL = "claude-sonnet-4-6"
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend" / "public" / "data"
MAX_CHANGES = 4


def select_changes(timeline: list[dict]) -> list[dict]:
    """Deterministically select up to MAX_CHANGES meaningful amendments.

    - dedupe by amendment_law_title (keep the diff_id-bearing entry, else latest date)
    - grounded = bool(diff_id)
    - order: grounded first, then enforcement_date descending
    """
    by_title: dict[str, dict] = {}
    for entry in timeline:
        title = entry.get("amendment_law_title", "")
        if not title:
            continue
        cand = {
            "source_title": title,
            "enforcement_date": entry.get("enforcement_date", "") or "",
            "diff_id": entry.get("diff_id"),
        }
        cur = by_title.get(title)
        if cur is None:
            by_title[title] = cand
            continue
        cur_has, cand_has = bool(cur["diff_id"]), bool(cand["diff_id"])
        if (cand_has and not cur_has) or (
            cand_has == cur_has and cand["enforcement_date"] > cur["enforcement_date"]
        ):
            by_title[title] = cand

    changes = [
        {
            "year": c["enforcement_date"][:4] if c["enforcement_date"] else "",
            "source_title": c["source_title"],
            "enforcement_date": c["enforcement_date"],
            "diff_id": c["diff_id"],
            "grounded": bool(c["diff_id"]),
        }
        for c in by_title.values()
    ]
    changes.sort(key=lambda c: (c["grounded"], c["enforcement_date"]), reverse=True)
    return changes[:MAX_CHANGES]
