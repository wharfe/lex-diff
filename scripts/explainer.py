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


def validate_explainer(explainer: dict, valid_years: set[str]) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    errors: list[str] = []
    for key in ("intro", "recent_changes", "faq"):
        if key not in explainer:
            errors.append(f"missing key: {key}")
    if errors:
        return errors

    intro = explainer["intro"]
    if not isinstance(intro, str) or not (40 <= len(intro) <= 200):
        errors.append("intro length out of range (40-200)")

    rc = explainer["recent_changes"]
    if not isinstance(rc, list) or not (1 <= len(rc) <= MAX_CHANGES):
        errors.append(f"recent_changes count out of range (1-{MAX_CHANGES})")
    else:
        for i, c in enumerate(rc):
            if not isinstance(c, dict):
                errors.append(f"recent_changes[{i}] not an object")
                continue
            for k in ("year", "title", "what", "grounded"):
                if k not in c:
                    errors.append(f"recent_changes[{i}] missing {k}")
            if c.get("year") not in valid_years:
                errors.append(f"recent_changes[{i}] year {c.get('year')} not in timeline")
            what = c.get("what", "")
            if not isinstance(what, str) or not (0 < len(what) <= 120):
                errors.append(f"recent_changes[{i}] what length out of range")
            if not c.get("grounded") and (c.get("why") or c.get("impact")):
                errors.append(f"recent_changes[{i}] ungrounded must not have why/impact")

    faq = explainer["faq"]
    if not isinstance(faq, list):
        errors.append("faq must be a list")
    else:
        for i, f in enumerate(faq):
            if not isinstance(f, dict):
                errors.append(f"faq[{i}] not an object")
                continue
            if not f.get("q") or not f.get("a"):
                errors.append(f"faq[{i}] missing q/a")
    return errors


def normalize_explainer(raw: dict, selected: list[dict]) -> dict:
    """Re-attach deterministic year/grounded from `selected`, keep LLM prose,
    strip why/impact from ungrounded changes, normalize faq to a clean list."""
    changes = []
    for sel, item in zip(selected, raw.get("recent_changes", []) or []):
        if not isinstance(item, dict):
            continue
        change = {
            "year": sel["year"],
            "title": (item.get("title") or sel["source_title"]).strip(),
            "what": (item.get("what") or "").strip(),
            "grounded": sel["grounded"],
        }
        if sel["grounded"]:
            why = (item.get("why") or "").strip()
            impact = (item.get("impact") or "").strip()
            if why:
                change["why"] = why
            if impact:
                change["impact"] = impact
        changes.append(change)

    raw_faq = raw.get("faq") or []
    if not isinstance(raw_faq, list):
        raw_faq = []
    faq = [
        {"q": f.get("q", "").strip(), "a": f.get("a", "").strip()}
        for f in raw_faq
        if isinstance(f, dict) and f.get("q") and f.get("a")
    ]
    return {"intro": (raw.get("intro") or "").strip(), "recent_changes": changes, "faq": faq}
