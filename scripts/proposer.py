"""Fetch bill proposer info from NDL Diet Records API.

Identifies who submitted each amendment bill (cabinet/member), which minister
explained it, and which committee reviewed it.

Usage:
    python scripts/proposer.py <amendment_law_title> <year>

Example:
    python scripts/proposer.py "民法等の一部を改正する法律" 2022
"""

import sys
import json
import re
from pathlib import Path

import httpx

NDL_API = "https://kokkai.ndl.go.jp/api/speech"
DATA_DIR = Path(__file__).parent.parent / "data" / "proposers"


def search_bill_speeches(bill_name: str, year: int) -> list[dict]:
    """Search NDL for speeches related to a bill."""
    # Remove 案 suffix if present for broader matching
    search_name = bill_name.rstrip("案")
    if not search_name.endswith("法律"):
        search_name += "案"
    else:
        search_name += "案"

    params = {
        "any": search_name,
        "from": f"{year}-01-01",
        "until": f"{year}-12-31",
        "recordPacking": "json",
        "maximumRecords": 50,
    }

    resp = httpx.get(NDL_API, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("speechRecord", [])


def extract_submission_type(speeches: list[dict], bill_name: str) -> str | None:
    """Determine if the bill was cabinet-submitted or member-submitted."""
    search = bill_name.rstrip("案") + "案"
    for rec in speeches:
        text = rec.get("speech", "")
        # Look for patterns like "内閣提出" near the bill name
        if search in text or bill_name in text:
            if "内閣提出" in text:
                return "閣法"
            if "衆議院提出" in text or "衆法" in text:
                return "衆法"
            if "参議院提出" in text or "参法" in text:
                return "参法"
    return None


def extract_minister(speeches: list[dict], bill_name: str) -> dict | None:
    """Find the minister who explained the bill's purpose."""
    search = bill_name.rstrip("案") + "案"
    for rec in speeches:
        text = rec.get("speech", "")
        position = rec.get("speakerPosition", "") or ""
        speaker = rec.get("speaker", "")

        # Look for 趣旨説明 or 提案理由 by a minister
        if ("大臣" in position or "大臣" in speaker) and (
            "趣旨" in text or "提案理由" in text
        ):
            if search in text or bill_name in text:
                return {
                    "name": speaker,
                    "position": position,
                    "party": rec.get("speakerGroup"),
                }
    return None


def extract_committee(speeches: list[dict], bill_name: str) -> str | None:
    """Find the committee that reviewed the bill."""
    search = bill_name.rstrip("案") + "案"
    committees = set()
    for rec in speeches:
        meeting = rec.get("nameOfMeeting", "")
        text = rec.get("speech", "")
        if meeting != "本会議" and (search in text or bill_name in text):
            committees.add(meeting)

    # Prefer the main reviewing committee (法務委員会, etc.)
    for c in committees:
        if "委員会" in c and "議院運営" not in c:
            return c
    return list(committees)[0] if committees else None


def fetch_proposer_info(amendment_law_title: str, promulgate_year: int) -> dict:
    """Fetch full proposer information for an amendment."""
    # Try the promulgation year and the year before
    speeches = []
    for year in [promulgate_year, promulgate_year - 1]:
        speeches = search_bill_speeches(amendment_law_title, year)
        if speeches:
            break

    if not speeches:
        return {
            "amendment_law_title": amendment_law_title,
            "submission_type": None,
            "minister": None,
            "committee": None,
            "found": False,
        }

    submission_type = extract_submission_type(speeches, amendment_law_title)
    minister = extract_minister(speeches, amendment_law_title)
    committee = extract_committee(speeches, amendment_law_title)

    return {
        "amendment_law_title": amendment_law_title,
        "submission_type": submission_type,
        "minister": minister,
        "committee": committee,
        "found": True,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    title = sys.argv[1]
    year = int(sys.argv[2])

    info = fetch_proposer_info(title, year)
    print(json.dumps(info, ensure_ascii=False, indent=2))

    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w]', '_', title)[:50]
    out_path = DATA_DIR / f"{safe_name}.json"
    out_path.write_text(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
