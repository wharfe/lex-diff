"""Enrich diff and timeline data with proposer information.

Reads existing diff/timeline JSON files, fetches proposer info from NDL,
and writes enriched data back.

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


def enrich_diff_files():
    """Add proposer info to all diff JSON files."""
    diff_dir = DATA_DIR / "diffs"
    if not diff_dir.exists():
        return

    for f in sorted(diff_dir.glob("*.json")):
        if f.name.endswith(".annotated.json"):
            continue

        data = json.loads(f.read_text())
        rev_after = data.get("revision_after", {})
        amendment_title = rev_after.get("amendment_law_title", "")

        if not amendment_title:
            continue

        # Skip if already enriched
        if data.get("proposer"):
            print(f"  Skip (already enriched): {f.name}")
            continue

        # Determine the year to search
        enforcement = rev_after.get("amendment_enforcement_date", "")
        year = int(enforcement[:4]) if enforcement else None
        if not year:
            continue

        print(f"  {amendment_title} ({year})...")
        try:
            info = fetch_proposer_info(amendment_title, year)
            if info.get("found"):
                data["proposer"] = {
                    "submission_type": info["submission_type"],
                    "minister": info["minister"],
                    "committee": info["committee"],
                }
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2))

                # Also update frontend copy
                frontend_path = FRONTEND_DIR / f.name
                if frontend_path.exists():
                    frontend_data = json.loads(frontend_path.read_text())
                    frontend_data["proposer"] = data["proposer"]
                    frontend_path.write_text(
                        json.dumps(frontend_data, ensure_ascii=False, indent=2)
                    )

                minister_name = info["minister"]["name"] if info["minister"] else "?"
                print(f"    -> {info['submission_type']} / {minister_name}")
            else:
                print(f"    -> Not found")
        except Exception as e:
            print(f"    -> Error: {e}")


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
    print("Enriching diff files...")
    enrich_diff_files()
    print("\nEnriching timeline files...")
    enrich_timeline_files()
    print("\nDone.")


if __name__ == "__main__":
    main()
