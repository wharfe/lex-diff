"""Generate AI annotations for law diffs.

Adds:
  1. PR-style summary (what changed, why, impact on citizens)
  2. Per-article annotations explaining each change in plain language
  3. Cross-reference resolution for cited articles

Usage:
    python scripts/annotate.py <diff_json_path>

Example:
    python scripts/annotate.py data/diffs/129AC0000000089_2024-03-31_2024-04-01.json
"""

import sys
import json
import os
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-20250514"


def load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def build_pr_summary_prompt(data: dict) -> str:
    """Build prompt for generating PR-style summary."""
    changed_articles = []
    for d in data["diffs"]:
        section = " > ".join(d["section_path"]) if d["section_path"] else ""
        title = d.get("title_after") or d.get("title_before") or ""
        change_type = {"added": "追加", "modified": "変更", "deleted": "削除"}[d["type"]]

        before_text = "\n".join(d["lines_before"][:10]) if d["lines_before"] else "(なし)"
        after_text = "\n".join(d["lines_after"][:10]) if d["lines_after"] else "(なし)"

        changed_articles.append(
            f"【{change_type}】{title}\n"
            f"所在: {section}\n"
            f"旧: {before_text}\n"
            f"新: {after_text}\n"
        )

    articles_text = "\n---\n".join(changed_articles)

    return f"""あなたは日本の法律の専門家であり、法律の改正内容を一般市民にわかりやすく説明する役割を担っています。

以下は「{data['law_title']}」の改正差分です（{data['date_before']} → {data['date_after']}）。
改正法令: {data['revision_after']['amendment_law_title']}

## 変更された条文（抜粋）

{articles_text}

## 指示

この改正について、GitHubのPull Requestの説明文のように、以下の構成でJSON形式で出力してください：

{{
  "title": "改正の要旨を1行で（例：共同親権制度の導入と嫡出推定規定の見直し）",
  "summary": "改正の全体像を3-5文で。専門用語を避け、国民生活への影響を中心に説明",
  "key_changes": [
    {{
      "theme": "変更テーマ（例：共同親権）",
      "description": "何がどう変わったかを2-3文で、具体的に"
    }}
  ],
  "impact": "この改正が国民の生活にどう影響するかを2-3文で",
  "background": "なぜこの改正が行われたかの背景を2-3文で"
}}

JSONのみを出力してください。"""


def build_article_annotation_prompt(diff_entry: dict, law_title: str, all_articles_context: str) -> str:
    """Build prompt for annotating a single article diff."""
    title = diff_entry.get("title_after") or diff_entry.get("title_before") or ""
    section = " > ".join(diff_entry["section_path"]) if diff_entry["section_path"] else ""
    change_type = {"added": "追加", "modified": "変更", "deleted": "削除"}[diff_entry["type"]]

    before_text = "\n".join(diff_entry["lines_before"]) if diff_entry["lines_before"] else "(なし)"
    after_text = "\n".join(diff_entry["lines_after"]) if diff_entry["lines_after"] else "(なし)"

    return f"""あなたは日本の法律の専門家です。以下の条文変更を一般市民にわかりやすく説明してください。

法令: {law_title}
条文: {title}
所在: {section}
変更種別: {change_type}

## 改正前の条文
{before_text}

## 改正後の条文
{after_text}

## 参考: 関連する他の条文（この法律内）
{all_articles_context}

## 指示

以下のJSON形式で出力してください：

{{
  "plain_summary": "この条文が何について定めているかを1文で（例：「子どもの父親が誰かを推定するルール」）",
  "change_description": "何がどう変わったかを2-3文で、専門用語を言い換えて説明",
  "cross_references": [
    {{
      "ref": "参照先の条文番号（例：第七百七十二条）",
      "article_num": "Num属性の値（例：772）",
      "context": "その参照が何を意味するかを1文で"
    }}
  ]
}}

JSONのみを出力してください。"""


def find_referenced_articles(text: str, all_articles: dict) -> str:
    """Extract articles referenced in the text and provide their content."""
    import re
    # Match patterns like 第七百七十二条, 第772条, etc.
    refs = set()
    # Full-width number references
    pattern = r'第[一二三四五六七八九十百千零〇]+条(?:の[一二三四五六七八九十百千]+)*'
    for match in re.finditer(pattern, text):
        refs.add(match.group())

    if not refs:
        return "(なし)"

    context_parts = []
    for ref in sorted(refs):
        # Try to find the article in our data
        for num, article_lines in all_articles.items():
            if ref in article_lines[0] if article_lines else False:
                context_parts.append(f"{ref}: {' '.join(article_lines[:3])}")
                break

    return "\n".join(context_parts) if context_parts else "(参照先の条文はこの差分データに含まれていません)"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    load_env()

    diff_path = Path(sys.argv[1])
    if not diff_path.exists():
        print(f"Error: {diff_path} not found")
        sys.exit(1)

    data = json.loads(diff_path.read_text())
    client = anthropic.Anthropic()

    # Build article context for cross-reference resolution
    all_articles = {}
    for d in data["diffs"]:
        num = d["article_num"]
        lines = d.get("lines_after") or d.get("lines_before") or []
        all_articles[num] = lines

    all_articles_text = "\n".join(
        f"{lines[0]}: {' '.join(lines[1:3])}"
        for lines in all_articles.values()
        if lines
    )

    # 1. Generate PR summary
    print("Generating PR summary...")
    pr_prompt = build_pr_summary_prompt(data)
    pr_response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": pr_prompt}],
    )
    pr_text = pr_response.content[0].text.strip()
    # Extract JSON from response
    if pr_text.startswith("```"):
        pr_text = pr_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    pr_summary = json.loads(pr_text)
    print(f"  Title: {pr_summary['title']}")

    # 2. Generate per-article annotations
    print(f"Annotating {len(data['diffs'])} articles...")
    annotations = {}
    for i, d in enumerate(data["diffs"]):
        num = d["article_num"]
        title = d.get("title_after") or d.get("title_before") or num
        print(f"  [{i+1}/{len(data['diffs'])}] {title}")

        prompt = build_article_annotation_prompt(d, data["law_title"], all_articles_text)
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            annotations[num] = json.loads(text)
        except json.JSONDecodeError:
            print(f"    Warning: Failed to parse annotation for {title}")
            annotations[num] = {
                "plain_summary": "",
                "change_description": text[:200],
                "cross_references": [],
            }

    # 3. Save annotated data
    data["pr_summary"] = pr_summary
    for d in data["diffs"]:
        num = d["article_num"]
        if num in annotations:
            d["annotation"] = annotations[num]

    out_path = diff_path.with_suffix(".annotated.json")
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nOutput: {out_path}")

    # Also copy to frontend
    frontend_data = Path(__file__).parent.parent / "frontend" / "public" / "data"
    frontend_path = frontend_data / diff_path.name
    frontend_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Frontend: {frontend_path}")


if __name__ == "__main__":
    main()
