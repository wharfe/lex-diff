"""Enrich diff and timeline data with proposer information.

Fetches each timeline entry's proposer from NDL (searched by promulgation
year), then copies it into the shipped diff for that revision.

Usage:
    python scripts/enrich.py
"""

import json
import re
from pathlib import Path

from proposer import fetch_proposer_info

DATA_DIR = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"


def extract_year_from_law_num(law_num: str) -> int | None:
    """Extract year from Japanese law number like '令和四年法律第百二号'."""
    era_map = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911, "明治": 1867}
    kanji_nums = {
        "元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
        "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    }

    for era, base in era_map.items():
        if era in law_num:
            m = re.search(rf'{era}(.+?)年', law_num)
            if m:
                year_str = m.group(1)
                if year_str in kanji_nums:
                    return base + kanji_nums[year_str]
                # Try numeric
                try:
                    return base + int(year_str)
                except ValueError:
                    pass
    return None


def proposer_from_timeline(diff: dict, timeline: dict) -> dict | None:
    """The proposer of the timeline entry for the diff's own revision.

    Searching NDL again for the diff by its enforcement year found a different
    year's bill whenever the title was a common one (道路交通法の一部を改正する
    法律 passes almost every year). The timeline entry was searched by its
    promulgation year, so the diff takes that answer instead of its own.
    """
    revision_id = diff.get("revision_after", {}).get("law_revision_id")
    for entry in timeline.get("timeline", []):
        if revision_id and entry.get("law_revision_id") == revision_id:
            return entry.get("proposer")
    return None


def diff_proposer(diff: dict, timeline: dict) -> dict | None:
    """A diff's proposer, or None when the diff carries several laws.

    One minister beside a diff that carries several same-day laws would credit
    the whole diff to one of them (#23). Counted from the timeline rather than
    the diff's own titles: a diff published before titles were collected
    (415AC 2025-04-01, held back by #28) names one law but carries two.
    """
    same_day = [
        e for e in timeline.get("timeline", [])
        if e.get("enforcement_date") == diff.get("date_after")
    ]
    if len(same_day) > 1:
        return None
    return proposer_from_timeline(diff, timeline)


def enrich_diff_files():
    """Copy each shipped diff's proposer from its law's timeline entry."""
    for f in sorted(FRONTEND_DIR.glob("*_*_*.json")):
        data = json.loads(f.read_text())
        timeline_path = FRONTEND_DIR / "timelines" / f"{data['law_id']}.json"
        if not timeline_path.exists():
            continue
        proposer = diff_proposer(data, json.loads(timeline_path.read_text()))
        if proposer == data.get("proposer"):
            continue
        if proposer is None:
            data.pop("proposer", None)
        else:
            data["proposer"] = proposer
        print(f"  {f.name}: {'set' if proposer else 'cleared'}")
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        # annotate.py rebuilds the shipped file from data/diffs, so the
        # proposer must be there too or a re-annotation drops it.
        for local in (DATA_DIR / "diffs" / f.name,):
            if local.exists():
                local_data = json.loads(local.read_text())
                if proposer is None:
                    local_data.pop("proposer", None)
                else:
                    local_data["proposer"] = proposer
                local.write_text(json.dumps(local_data, ensure_ascii=False, indent=2))


def enrich_timeline_files():
    """Add proposer info to timeline entries."""
    timeline_dir = DATA_DIR / "timelines"
    if not timeline_dir.exists():
        return

    for f in sorted(timeline_dir.glob("*.json")):
        data = json.loads(f.read_text())
        changed = False

        for entry in data.get("timeline", []):
            if entry.get("proposer"):
                continue

            amendment_title = entry.get("amendment_law_title", "")
            if not amendment_title:
                continue

            enforcement = entry.get("enforcement_date", "")
            year = int(enforcement[:4]) if enforcement else None
            promulgate = entry.get("promulgate_date", "")
            promulgate_year = int(promulgate[:4]) if promulgate else year
            if not promulgate_year:
                continue

            print(f"  {amendment_title[:40]}... ({promulgate_year})")
            try:
                info = fetch_proposer_info(amendment_title, promulgate_year)
                if info.get("found"):
                    entry["proposer"] = {
                        "submission_type": info["submission_type"],
                        "minister": info["minister"],
                        "committee": info["committee"],
                    }
                    minister_name = info["minister"]["name"] if info["minister"] else "?"
                    print(f"    -> {info['submission_type']} / {minister_name}")
                    changed = True
                else:
                    print(f"    -> Not found")
            except Exception as e:
                print(f"    -> Error: {e}")

        if changed:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            # Update frontend copy
            frontend_path = FRONTEND_DIR / "timelines" / f.name
            if frontend_path.exists():
                frontend_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2)
                )


def main():
    # Timelines first: a diff's proposer is copied from its timeline entry.
    print("Enriching timeline files...")
    enrich_timeline_files()
    print("\nEnriching diff files...")
    enrich_diff_files()
    print("\nDone.")


if __name__ == "__main__":
    main()
