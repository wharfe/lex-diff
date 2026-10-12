"""Publish not-yet-enforced amendments as diffs, with no AI prose.

Usage:
    python scripts/pending.py <law_id>... | --all [--check]

Each pending enforcement date D becomes the pair (D-1, D), exactly like an
enforced diff, so stacked pending amendments separate by date. The D-1 text
already carries every amendment scheduled before D: it is not today's law, and
the diff records which pending amendments it contains (`unenforced_before`).

Whether a revision is pending, and its date, come from a law_revisions list
fetched in this run — never from data/raw, whose age nothing records (the same
reason law_summary.py fetches its own evidence).

--check writes nothing. It re-fetches everything, rebuilds every pending diff
through the same process_law, and compares content with what ships: e-Gov
updates a pending revision's text without changing its id, so ids and dates
cannot stand in for the text. Anything that differs, no longer appears, or is
not shipped yet is reported and the exit status is 1. Deleting or regenerating
a published page is a human call.
"""

import datetime
import json
import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import diff
import fetch

JST = ZoneInfo("Asia/Tokyo")
ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
# Snapshots of future dates live apart from data/raw: diff.py reads
# data/raw/<law>_<date>.json without asking when it was fetched, and a pending
# text read back after its date would become an enforced diff with old content.
PENDING_RAW_DIR = RAW_DIR / "pending"
SHIPPED_DIR = ROOT / "frontend" / "public" / "data"
OUT_DIRS = (ROOT / "data" / "diffs", SHIPPED_DIR)
TIMELINE_DIR = SHIPPED_DIR / "timelines"

# Fields that change without the law changing: when the doc was built, and
# what enrich.py copies in afterwards.
VOLATILE_KEYS = ("proposer",)


def today_jst() -> str:
    return datetime.datetime.now(JST).date().isoformat()


def pending_dates(revisions: list[dict], today: str) -> dict[str, list[dict]]:
    """Unenforced revisions dated after today, grouped by date, oldest first."""
    out: dict[str, list[dict]] = {}
    for r in revisions:
        if r.get("current_revision_status") != "UnEnforced":
            continue
        date = r.get("amendment_enforcement_date")
        if not date:
            raise ValueError(f"unenforced revision without a date: {r.get('law_revision_id')}")
        if date > today:
            out.setdefault(date, []).append(r)
    return dict(sorted(out.items()))


def _describe(r: dict) -> dict:
    return {
        "law_revision_id": r["law_revision_id"],
        "amendment_law_title": r.get("amendment_law_title"),
        "amendment_law_num": r.get("amendment_law_num"),
        # Present only while the date is not fixed (measured: 22 of 30 pending
        # revisions, never on an enforced one). Shown verbatim, never reworded.
        "enforcement_comment": r.get("amendment_enforcement_comment") or None,
        "scheduled_enforcement_date": r.get("amendment_scheduled_enforcement_date"),
    }


def unenforced_before(revisions: list[dict], date: str, today: str) -> list[dict]:
    """Pending revisions that the D-1 text already contains."""
    found = [
        r for r in revisions
        if r.get("current_revision_status") == "UnEnforced"
        and today < (r.get("amendment_enforcement_date") or "") < date
    ]
    found.sort(key=lambda r: (r["amendment_enforcement_date"], r["law_revision_id"]))
    return [_describe(r) | {"enforcement_date": r["amendment_enforcement_date"]} for r in found]


def pending_block(revs: list[dict], generated_on: str, before: list[dict]) -> dict:
    return {
        "generated_on": generated_on,
        "revisions": [_describe(r) for r in revs],
        "unenforced_before": before,
    }


def _expected_before_ids(revisions: list[dict], date: str) -> set[str]:
    """Revision ids e-Gov should return for D-1: the latest dated before D."""
    earlier = [r for r in revisions if (r.get("amendment_enforcement_date") or "") < date
               and r.get("amendment_enforcement_date")]
    if not earlier:
        return set()
    last = max(r["amendment_enforcement_date"] for r in earlier)
    return {r["law_revision_id"] for r in earlier if r["amendment_enforcement_date"] == last}


def process_law(
    law_id: str,
    revisions: list[dict],
    fetch_data: Callable[[str, str], dict],
    today: str,
    shipped_ids: frozenset[str],
) -> dict:
    """Build every pending diff of one law. Fetches through `fetch_data`, writes nothing.

    A pair that ships already but now has a changed table or no change at all is
    an error, not a skip: the old page would go on showing changes that are not
    what e-Gov now holds (the same rule as diff.py's no-change refusal).
    """
    result: dict = {"docs": {}, "raws": {}, "published": [], "withheld": [],
                    "skipped": [], "errors": []}
    try:
        by_date = pending_dates(revisions, today)
    except ValueError as e:
        result["errors"].append(f"{law_id}: {e}")
        return result

    for date, revs in by_date.items():
        before_date = (datetime.date.fromisoformat(date) - timedelta(days=1)).isoformat()
        diff_id = f"{law_id}_{before_date}_{date}"
        try:
            before = fetch_data(law_id, before_date)
            after = fetch_data(law_id, date)
        except Exception as e:  # network or HTTP error: this pair only
            result["errors"].append(f"{diff_id}: fetch failed: {e}")
            continue

        own_ids = {r["law_revision_id"] for r in revs}
        after_id = after["revision_info"].get("law_revision_id")
        if after_id not in own_ids:
            result["errors"].append(
                f"{diff_id}: e-Gov returned {after_id!r} for {date}, expected one of {sorted(own_ids)}")
            continue
        before_id = before["revision_info"].get("law_revision_id")
        expected = _expected_before_ids(revisions, date)
        if before_id not in expected:
            # Another version as the "before" side would mix several amendments
            # into one diff and credit them to this one.
            result["errors"].append(
                f"{diff_id}: e-Gov returned {before_id!r} for {before_date}, expected one of {sorted(expected)}")
            continue

        # Same order as diff.main: tables first, since a table-only amendment
        # also comes out of compute_diff as no change.
        shipped = diff_id in shipped_ids
        if diff.tables_changed(before["law_full_text"], after["law_full_text"]):
            if shipped:
                result["errors"].append(f"{diff_id}: published, but a table now changes (#28)")
            else:
                result["withheld"].append(diff_id)
            continue
        try:
            doc = diff.build_diff_document(law_id, before_date, date, before, after, revisions)
        except ValueError as e:
            result["errors"].append(f"{diff_id}: {e}")
            continue
        if not doc["diffs"]:
            if shipped:
                result["errors"].append(f"{diff_id}: published, but the pair now has no changes")
            else:
                result["skipped"].append(diff_id)
            continue

        doc["pending"] = pending_block(revs, today, unenforced_before(revisions, date, today))
        result["docs"][diff_id] = doc
        result["published"].append(diff_id)
        result["raws"][f"{law_id}_{before_date}.json"] = before
        result["raws"][f"{law_id}_{date}.json"] = after
    return result


def comparable(doc: dict) -> dict:
    """The doc minus what changes without the law changing."""
    out = {k: v for k, v in doc.items() if k not in VOLATILE_KEYS}
    if "pending" in out:
        out["pending"] = {k: v for k, v in out["pending"].items() if k != "generated_on"}
    return out


def check(shipped: dict[str, dict[str, dict]], fresh: dict[str, dict]) -> list[str]:
    """Problems between shipped pending diffs and a fresh rebuild, per law."""
    problems: list[str] = []
    for law_id, result in fresh.items():
        problems.extend(result["errors"])
        ships = shipped.get(law_id, {})
        for diff_id, doc in ships.items():
            new = result["docs"].get(diff_id)
            if new is None:
                problems.append(
                    f"{diff_id}: no longer a pending diff (enforced, date moved, or withheld) — "
                    "regenerate through fetch.py → diff.py → annotate.py, or remove")
            elif comparable(new) != comparable(doc):
                problems.append(f"{diff_id}: e-Gov now holds different content — re-run pending.py")
        for diff_id in result["docs"]:
            if diff_id not in ships:
                problems.append(f"{diff_id}: pending but not shipped — run pending.py")
    return problems


def shipped_pending(law_id: str) -> dict[str, dict]:
    out = {}
    for path in sorted(SHIPPED_DIR.glob(f"{law_id}_*_*.json")):
        doc = json.loads(path.read_text())
        if "pending" in doc:
            out[path.stem] = doc
    return out


def all_law_ids() -> list[str]:
    return sorted(p.stem for p in TIMELINE_DIR.glob("*.json"))


def main() -> None:
    args = sys.argv[1:]
    checking = "--check" in args
    args = [a for a in args if a != "--check"]
    if not args:
        print(__doc__)
        sys.exit(1)
    law_ids = all_law_ids() if args == ["--all"] else args

    today = today_jst()
    fresh: dict[str, dict] = {}
    revision_lists: dict[str, dict] = {}
    shipped: dict[str, dict[str, dict]] = {}
    for law_id in law_ids:
        print(f"{law_id}: fetching revisions...")
        data = fetch.fetch_law_revisions(law_id)
        revision_lists[law_id] = data
        shipped[law_id] = shipped_pending(law_id)
        fresh[law_id] = process_law(
            law_id, data["revisions"], fetch.fetch_law_data, today,
            frozenset(shipped[law_id]))
        r = fresh[law_id]
        print(f"  pending diffs: {len(r['published'])}, withheld (tables): {len(r['withheld'])}, "
              f"no change: {len(r['skipped'])}, errors: {len(r['errors'])}")

    if today_jst() != today:
        # "Pending" was decided against `today`; a doc stamped with it must not
        # be saved, or compared, on another day.
        print(f"Error: the JST date changed from {today} during the run. Nothing written.")
        sys.exit(1)

    if checking:
        problems = check(shipped, fresh)
        for p in problems:
            print(f"PROBLEM: {p}")
        print(f"{len(problems)} problem(s).")
        sys.exit(1 if problems else 0)

    PENDING_RAW_DIR.mkdir(parents=True, exist_ok=True)
    for law_id, result in fresh.items():
        # The list timeline.py links from; fetched in this run.
        (RAW_DIR / f"{law_id}_revisions.json").write_text(
            json.dumps(revision_lists[law_id], ensure_ascii=False, indent=2))
        for name, data in result["raws"].items():
            (PENDING_RAW_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))
        for diff_id, doc in result["docs"].items():
            old = shipped[law_id].get(diff_id)
            if old is not None and comparable(old) == comparable(doc):
                continue  # unchanged: keep generated_on and enrich's proposer
            for out_dir in OUT_DIRS:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / f"{diff_id}.json").write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2))
            print(f"  wrote {diff_id}")
        for e in result["errors"]:
            print(f"ERROR: {e}")
        for w in result["withheld"]:
            print(f"WITHHELD (tables changed, #28): {w}")

    print("Next: timeline.py for each law, then enrich.py.")
    if any(r["errors"] for r in fresh.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
