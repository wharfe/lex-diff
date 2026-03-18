"""Generate timeline data for a law's revision history.

Usage:
    python scripts/timeline.py <law_id>

Example:
    python scripts/timeline.py 129AC0000000089
"""

import sys
import json
from pathlib import Path

import httpx

BASE_URL = "https://laws.e-gov.go.jp/api/2"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"


def fetch_revisions(law_id: str) -> dict:
    """Fetch revision history for a law."""
    cache_path = RAW_DIR / f"{law_id}_revisions.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    url = f"{BASE_URL}/law_revisions/{law_id}"
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def fetch_law_title(law_id: str) -> str:
    """Fetch the current title of a law."""
    url = f"{BASE_URL}/law_data/{law_id}"
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["revision_info"]["law_title"]


def build_timeline(law_id: str) -> dict:
    """Build timeline data from revision history."""
    data = fetch_revisions(law_id)
    law_info = data["law_info"]
    revisions = data["revisions"]

    # Sort by enforcement date (newest first)
    revisions.sort(key=lambda r: r["amendment_enforcement_date"], reverse=True)

    # Get law title from the first revision
    law_title = revisions[0]["law_title"] if revisions else ""

    # Check which diffs we already have
    diff_dir = DATA_DIR / "diffs"
    existing_diffs = set()
    if diff_dir.exists():
        for f in diff_dir.iterdir():
            if f.suffix == ".json" and law_id in f.name:
                existing_diffs.add(f.stem)

    timeline_entries = []
    for i, rev in enumerate(revisions):
        enforcement_date = rev["amendment_enforcement_date"]
        amendment_title = rev.get("amendment_law_title", "")
        promulgate_date = rev.get("amendment_promulgate_date", "")

        # Find the previous revision to determine diff dates
        prev_date = None
        if i + 1 < len(revisions):
            prev_date = revisions[i + 1]["amendment_enforcement_date"]

        # Check if diff exists
        diff_id = None
        if prev_date:
            # Diff is computed between day before enforcement and enforcement day
            from datetime import datetime, timedelta
            enforce_dt = datetime.strptime(enforcement_date, "%Y-%m-%d")
            before_date = (enforce_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            candidate = f"{law_id}_{before_date}_{enforcement_date}"
            if candidate in existing_diffs:
                diff_id = candidate

        timeline_entries.append({
            "enforcement_date": enforcement_date,
            "promulgate_date": promulgate_date,
            "amendment_law_title": amendment_title,
            "law_revision_id": rev["law_revision_id"],
            "diff_id": diff_id,
        })

    output = {
        "law_id": law_id,
        "law_title": law_title,
        "law_num": law_info.get("law_num", ""),
        "promulgation_date": law_info.get("promulgation_date", ""),
        "revision_count": len(revisions),
        "timeline": timeline_entries,
    }

    out_dir = DATA_DIR / "timelines"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{law_id}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    # Also copy to frontend
    frontend_dir = Path(__file__).parent.parent / "frontend" / "public" / "data" / "timelines"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / f"{law_id}.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2)
    )

    print(f"Law: {law_title} ({law_info.get('law_num', '')})")
    print(f"Revisions: {len(revisions)}")
    print(f"Output: {out_path}")

    return output


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    law_id = sys.argv[1]
    build_timeline(law_id)


if __name__ == "__main__":
    main()
