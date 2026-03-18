"""Fetch law data from e-Gov Law API v2.

Usage:
    python scripts/fetch.py <law_id> <date_before> <date_after>

Example:
    python scripts/fetch.py 129AC0000000089 2024-03-31 2024-04-01
"""

import sys
import json
import httpx
from pathlib import Path

BASE_URL = "https://laws.e-gov.go.jp/api/2"
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


def fetch_law_data(law_id: str, asof: str) -> dict:
    """Fetch law data at a specific point in time."""
    url = f"{BASE_URL}/law_data/{law_id}"
    params = {"asof": asof}
    resp = httpx.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_law_revisions(law_id: str) -> dict:
    """Fetch revision history for a law."""
    url = f"{BASE_URL}/law_revisions/{law_id}"
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    law_id = sys.argv[1]
    date_before = sys.argv[2]
    date_after = sys.argv[3]

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching revisions for {law_id}...")
    revisions = fetch_law_revisions(law_id)
    rev_path = DATA_DIR / f"{law_id}_revisions.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False, indent=2))
    print(f"  -> {rev_path}")

    print(f"Fetching law data as of {date_before}...")
    before = fetch_law_data(law_id, date_before)
    before_path = DATA_DIR / f"{law_id}_{date_before}.json"
    before_path.write_text(json.dumps(before, ensure_ascii=False, indent=2))
    print(f"  -> {before_path}")

    print(f"Fetching law data as of {date_after}...")
    after = fetch_law_data(law_id, date_after)
    after_path = DATA_DIR / f"{law_id}_{date_after}.json"
    after_path.write_text(json.dumps(after, ensure_ascii=False, indent=2))
    print(f"  -> {after_path}")

    print("Done.")


if __name__ == "__main__":
    main()
