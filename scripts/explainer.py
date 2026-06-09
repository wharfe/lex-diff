"""Generate a plain-language 'recent amendments' explainer for a law using Claude AI.

Usage:
    python scripts/explainer.py <law_id>

Example:
    python scripts/explainer.py 416AC0000000123
"""

import sys
import json
import os
import anthropic
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


def load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def load_pr_summary(diff_id: str) -> dict | None:
    """Load pr_summary for a diff_id from the frontend data dir or data/diffs."""
    for base in (FRONTEND_DIR, DATA_DIR / "diffs"):
        path = base / f"{diff_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return data.get("pr_summary")
    return None


def build_prompt(law_title, law_num, category, summary_desc, changes):
    lines = []
    for i, c in enumerate(changes):
        block = [f"[改正{i + 1}] 施行年: {c['year']} / 改正法: {c['source_title']}"]
        if c["grounded"]:
            pr = c.get("pr_summary") or {}
            block.append("  根拠あり(grounded)。以下の差分要約に基づき、what/why/impactを書いてよい:")
            block.append(f"    タイトル: {pr.get('title', '')}")
            block.append(f"    概要: {pr.get('summary', '')}")
            block.append(f"    背景: {pr.get('background', '')}")
            block.append(f"    影響: {pr.get('impact', '')}")
        else:
            block.append("  根拠なし(ungrounded)。改正法名と施行年のみ確認済み。"
                         "whatは改正法名から言える範囲に留め、why/impactは書かないこと。")
        lines.append("\n".join(block))
    changes_text = "\n\n".join(lines)

    return f"""あなたは日本の法律をわかりやすく解説する専門家です。以下の法律の「最近の改正」を、一般市民向けにJSON形式で解説してください。

法令名: {law_title}
法令番号: {law_num}
分類: {category}
法律の概要: {summary_desc}

最近の主要改正（この{len(changes)}件についてのみ書く。順番・件数を変えない）:
{changes_text}

出力JSON形式:
{{
  "intro": "この法律で近年どんな改正が続いているかの導入（80-150字、専門用語を避ける）",
  "recent_changes": [
    {{"title": "改正の通称（例: 相続登記の義務化）", "what": "何が変わったか（40-100字）", "why": "なぜ変わったか（grounded時のみ・40-100字）", "impact": "私たちへの影響（grounded時のみ・40-100字）"}}
  ],
  "faq": [
    {{"q": "よくある質問（例: いつから？）", "a": "回答（40-120字）"}}
  ]
}}

ルール:
- recent_changes は入力の改正と同じ順番・同じ件数で出力する。
- ungrounded の改正では why/impact を出力しない（キーごと省略）。
- 提供情報に無い事実（数値・期限・因果）を断定しない。不確実なら書かない。
- 見出しや本文に「{law_title}」「改正」「わかりやすく」が自然に含まれるとよい。
- faq は0-3件。確実に答えられるものだけ。
- JSONのみを出力する。"""


def generate_explainer(law_title, law_num, category, summary_desc, changes) -> dict:
    client = anthropic.Anthropic()
    prompt = build_prompt(law_title, law_num, category, summary_desc, changes)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
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

    timeline_path = DATA_DIR / "timelines" / f"{law_id}.json"
    if not timeline_path.exists():
        print(f"Error: Run timeline.py first for {law_id}")
        sys.exit(1)
    timeline = json.loads(timeline_path.read_text())

    changes = select_changes(timeline["timeline"])
    if not changes:
        print(f"Error: no usable amendments for {law_id}")
        sys.exit(1)
    for c in changes:
        if c["grounded"] and c["diff_id"]:
            c["pr_summary"] = load_pr_summary(c["diff_id"])
            if not c["pr_summary"]:
                # diff file missing -> downgrade to ungrounded for safety
                c["grounded"] = False

    print(f"Generating explainer for {timeline['law_title']} ({len(changes)} changes)...")
    raw = generate_explainer(
        timeline["law_title"],
        timeline["law_num"],
        timeline.get("category", ""),
        (timeline.get("summary") or {}).get("description", ""),
        changes,
    )
    explainer = normalize_explainer(raw, changes)

    valid_years = {e.get("enforcement_date", "")[:4] for e in timeline["timeline"]}
    errors = validate_explainer(explainer, valid_years)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        print("\nGenerated (not saved):")
        print(json.dumps(explainer, ensure_ascii=False, indent=2))
        sys.exit(2)

    timeline["explainer"] = explainer
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    frontend_path = FRONTEND_DIR / "timelines" / f"{law_id}.json"
    if frontend_path.exists():
        frontend_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))

    print(f"  intro: {explainer['intro'][:60]}...")
    print(f"  recent_changes: {len(explainer['recent_changes'])}, faq: {len(explainer['faq'])}")
    print(f"  Saved: {timeline_path}")


if __name__ == "__main__":
    main()
