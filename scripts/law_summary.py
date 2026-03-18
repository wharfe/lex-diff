"""Generate a brief summary for a law using Claude AI.

Usage:
    python scripts/law_summary.py <law_id>

Example:
    python scripts/law_summary.py 129AC0000000089
"""

import sys
import json
import os
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-20250514"
DATA_DIR = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def generate_summary(law_title: str, law_num: str, category: str, revision_count: int) -> dict:
    """Generate a brief plain-language summary of a law."""
    client = anthropic.Anthropic()

    prompt = f"""あなたは日本の法律の専門家です。以下の法律について、一般市民向けの簡潔な説明をJSON形式で出力してください。

法令名: {law_title}
法令番号: {law_num}
分類: {category}
改正回数: {revision_count}回

以下のJSON形式で出力してください：

{{
  "description": "この法律が何を定めているかを2-3文で（専門用語を避け、日常生活との関わりを含めて）",
  "scope": "この法律の適用範囲を1文で（例：すべての国民、事業者、特定の業種など）",
  "keywords": ["関連キーワード", "最大5つ"]
}}

JSONのみを出力してください。"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    load_env()
    law_id = sys.argv[1]

    # Load timeline data
    timeline_path = DATA_DIR / "timelines" / f"{law_id}.json"
    if not timeline_path.exists():
        print(f"Error: Run timeline.py first for {law_id}")
        sys.exit(1)

    timeline = json.loads(timeline_path.read_text())

    # Get category from revision data
    rev_path = DATA_DIR / "raw" / f"{law_id}_revisions.json"
    category = ""
    if rev_path.exists():
        rev_data = json.loads(rev_path.read_text())
        if rev_data.get("revisions"):
            category = rev_data["revisions"][0].get("category", "")

    print(f"Generating summary for {timeline['law_title']}...")
    summary = generate_summary(
        timeline["law_title"],
        timeline["law_num"],
        category,
        timeline["revision_count"],
    )
    print(f"  Description: {summary['description'][:80]}...")

    # Extract unique contributors from timeline
    contributors = {}
    for entry in timeline.get("timeline", []):
        proposer = entry.get("proposer")
        if proposer and proposer.get("minister") and proposer["minister"].get("name"):
            minister = proposer["minister"]
            name = minister["name"]
            if name not in contributors:
                contributors[name] = {
                    "name": name,
                    "position": minister.get("position", ""),
                    "party": minister.get("party"),
                    "count": 0,
                }
            contributors[name]["count"] += 1

    # Sort by count descending
    contributor_list = sorted(contributors.values(), key=lambda x: x["count"], reverse=True)

    # Update timeline data
    timeline["summary"] = summary
    timeline["category"] = category
    timeline["contributors"] = contributor_list

    # Save
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))

    # Update frontend
    frontend_path = FRONTEND_DIR / "timelines" / f"{law_id}.json"
    if frontend_path.exists():
        frontend_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))

    print(f"  Contributors: {len(contributor_list)}")
    print(f"  Saved: {timeline_path}")


if __name__ == "__main__":
    main()
