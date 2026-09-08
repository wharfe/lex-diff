"""Generate a brief summary for a law using Claude AI.

Usage:
    python scripts/law_summary.py <law_id>

Example:
    python scripts/law_summary.py 129AC0000000089

Unlike annotate.py and explainer.py, this script hands the model no law text —
only the law's name, number, category and revision count. Everything else comes
out of the model's own memory.

validate_summary() is a narrow guard against one known failure, not a guarantee
that the answer is true. It checks the shape and rejects the penalty names
abolished in 2025; a wrong scope, a different repealed institution, or an
invented requirement passes it untouched. Removing the class of error entirely
means handing the model the current article text as evidence, the way the other
two scripts already do — issue #16.
"""

import sys
import json
import os
from pathlib import Path

import anthropic
from llm import complete_json
from lawtext import extract_text, walk_tags

MODEL = "claude-sonnet-5"
DATA_DIR = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"

# Penalty names abolished on 2025-06-01, when 懲役 and 禁錮 were merged into
# 拘禁刑. A law summary describes the law as it stands now, so these words can
# never be right here — unlike a diff's pr_summary, which legitimately says
# "懲役 was renamed to 拘禁刑" about the amendment that did the renaming.
#
# 禁固 and 禁こ are the newspaper spellings of 禁錮; a model reaches for them as
# readily as for the 常用漢字 form, and a ban that lists only 禁錮 would let the
# same mistake through one character later.
#
# This is deliberately context-blind, and that costs something: a summary that
# says, correctly, "懲役 and 禁錮 were merged into 拘禁刑 in 2025" is rejected too.
# That is the safe direction to fail — the script exits without saving and the
# next run rewrites the sentence, whereas the other direction publishes an
# abolished penalty as current law, which is the bug this exists for.
ABOLISHED_PENALTY_TERMS = ("懲役", "禁錮", "禁固", "禁こ")

MAX_KEYWORDS = 5

# Headings that make up a law's table of contents, outermost first.
STRUCTURE_TITLE_TAGS = {"PartTitle", "ChapterTitle", "SectionTitle", "SubsectionTitle"}

# 附則 is a different axis from the main text and says nothing about what the
# law is for, so the evidence stops at its boundary.
SUPPL = {"SupplProvision"}


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def build_evidence(law_full_text: dict) -> str:
    """The law's own text, cut down to what a summary can be written from.

    Three things, and deliberately not the whole law: 民法 is 226,000
    characters and does not fit in a prompt at any useful price.

    - the table of contents, which is the law's own account of its shape
    - every article caption, which together are the list of what it covers
      (1,250 of them in 民法, 17,823 characters — dense and cheap)
    - article 1 in full, which is the purpose / scope clause and so the direct
      basis for the summary's `scope` field. 刑法第一条 reads "日本国内において
      罪を犯したすべての者に適用する" — that *is* the answer, verbatim.

    Raises rather than returning something empty: calling the model with no
    evidence is what let it write from memory in the first place.
    """
    headings = [
        extract_text(n).strip()
        for n in walk_tags(law_full_text, STRUCTURE_TITLE_TAGS, stop_at=SUPPL)
    ]
    captions = [
        extract_text(n).strip()
        for n in walk_tags(law_full_text, {"ArticleCaption"}, stop_at=SUPPL)
    ]
    articles = walk_tags(law_full_text, {"Article"}, stop_at=SUPPL)
    first_article = extract_text(articles[0]).strip() if articles else ""

    if not (headings or captions or first_article):
        raise ValueError(
            "no law text to summarise — refusing to call the model with empty "
            "evidence (it would answer from memory)"
        )

    parts = []
    if headings:
        parts.append("## 目次\n" + "\n".join(h for h in headings if h))
    if captions:
        parts.append("## 各条の見出し\n" + "\n".join(c for c in captions if c))
    if first_article:
        parts.append("## 第一条（全文）\n" + first_article)
    return "\n\n".join(parts)


def load_evidence(raw_dir: Path, law_id: str) -> str:
    """Build evidence from the newest snapshot of a law in `raw_dir`.

    Newest, not any: a summary describes the law as it stands now, and
    data/raw holds one file per point-in-time fetch. The `_revisions.json`
    companion has no law_full_text and is skipped by the same test that skips
    a malformed snapshot.
    """
    snapshots = []
    for path in sorted(raw_dir.glob(f"{law_id}_*.json")):
        try:
            body = json.loads(path.read_text()).get("law_full_text")
        except json.JSONDecodeError:
            continue
        if body:
            snapshots.append((path.name, body))
    if not snapshots:
        raise FileNotFoundError(
            f"no snapshot with law_full_text for {law_id} in {raw_dir} — "
            "run fetch.py first; a summary is not written without the law text"
        )
    return build_evidence(snapshots[-1][1])


def validate_summary_shape(summary: dict) -> list[str]:
    """The checks that can be made without the law text in hand.

    Split out from validate_summary because the two run in different places.
    A shipped summary is checked long after generation, from a repository that
    does not carry data/raw (it is gitignored, so CI has no snapshots at all);
    all that can be asked of it there is that it is well formed and free of the
    abolished penalty names. Grounding needs the evidence and so belongs to
    generation time only — see validate_summary below.
    """
    errors: list[str] = []
    if not isinstance(summary, dict):
        return ["summary is not an object"]
    for key in ("description", "scope", "keywords"):
        if key not in summary:
            errors.append(f"missing key: {key}")
    if errors:
        return errors

    description = summary["description"]
    if not isinstance(description, str) or not (40 <= len(description) <= 400):
        errors.append("description length out of range (40-400)")

    scope = summary["scope"]
    if not isinstance(scope, str) or not (5 <= len(scope) <= 200):
        errors.append("scope length out of range (5-200)")

    keywords = summary["keywords"]
    if not isinstance(keywords, list) or not (1 <= len(keywords) <= MAX_KEYWORDS):
        errors.append(f"keywords count out of range (1-{MAX_KEYWORDS})")
    elif not all(isinstance(k, str) and k.strip() for k in keywords):
        errors.append("keywords must all be non-empty strings")

    blob = json.dumps(summary, ensure_ascii=False)
    for term in ABOLISHED_PENALTY_TERMS:
        if term in blob:
            errors.append(
                f"abolished penalty name in summary: {term}"
                " (懲役・禁錮 were merged into 拘禁刑 on 2025-06-01)"
            )
    return errors


def validate_summary(summary: dict, evidence: str) -> list[str]:
    """Shape, plus: every keyword must actually occur in the law's own text.

    `evidence` is required rather than optional so that a caller which lost it
    fails loudly instead of quietly falling back to the memory-only behaviour
    this function exists to end.

    A keyword is a noun: either the law contains the word or it does not. Prose
    cannot be checked this way — a summary may fairly say 事業者 or 日常生活
    without the statute using either word — but an invented institution almost
    always surfaces in the keywords first, and catching it there costs nothing.
    """
    if not evidence or not evidence.strip():
        return ["evidence is empty — refusing to validate a summary with no basis"]

    errors = validate_summary_shape(summary)
    keywords = summary.get("keywords") if isinstance(summary, dict) else None
    if isinstance(keywords, list):
        for kw in keywords:
            if isinstance(kw, str) and kw.strip() and kw.strip() not in evidence:
                errors.append(
                    f"keyword not found in the law text: {kw}"
                    " (keywords must come from the law's own headings or article 1)"
                )
    return errors


def generate_summary(
    law_title: str,
    law_num: str,
    category: str,
    revision_count: int,
    evidence: str,
) -> dict:
    """Generate a brief plain-language summary of a law from its own text."""
    client = anthropic.Anthropic()

    prompt = f"""あなたは日本の法律の専門家です。以下の法律について、一般市民向けの簡潔な説明をJSON形式で出力してください。

法令名: {law_title}
法令番号: {law_num}
分類: {category}
改正回数: {revision_count}回

--- 以下はこの法律の実際の条文から機械的に抜き出した根拠です ---

{evidence}

--- 根拠ここまで ---

制約:
- 上の根拠に書かれていることだけを使って書いてください。根拠に無い制度・用語・数値を補わないでください。
- keywords は必ず根拠テキストに現れる語から選んでください（現れない語は機械的に弾かれ、やり直しになります）。
- 根拠は目次・各条の見出し・第一条だけで、条文本文の大部分は含まれていません。書かれていない細部を推測で埋めないでください。
- 2025年6月1日施行の改正刑法により「懲役」「禁錮」は「拘禁刑」に一本化されました。現行制度の説明にこれらの刑名を使わないでください。
- 現在の制度として言えることだけを書き、廃止された制度名・過去の呼称を現行のものとして提示しないでください。

以下のJSON形式で出力してください：

{{
  "description": "この法律が何を定めているかを2-3文で（専門用語を避け、日常生活との関わりを含めて）",
  "scope": "この法律の適用範囲を1文で（例：すべての国民、事業者、特定の業種など）",
  "keywords": ["関連キーワード", "最大5つ"]
}}

JSONのみを出力してください。"""

    return complete_json(client, MODEL, prompt, max_tokens=4000)


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

    # The law's own text, not the model's memory. Raises when there is no
    # snapshot: a summary is not written without evidence.
    evidence = load_evidence(DATA_DIR / "raw", law_id)

    print(f"Generating summary for {timeline['law_title']}...")
    print(f"  Evidence: {len(evidence)} chars from the law text")
    summary = generate_summary(
        timeline["law_title"],
        timeline["law_num"],
        category,
        timeline["revision_count"],
        evidence,
    )

    errors = validate_summary(summary, evidence)
    if errors:
        print("Validation failed — nothing was saved:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(2)

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
