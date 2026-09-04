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

import hashlib
import sys
import json
import os
from pathlib import Path

import anthropic
from difflib import SequenceMatcher

from llm import complete_json

MODEL = "claude-sonnet-5"

# Bump when a prompt changes so cached annotations written by the old prompt
# are not reused. Part of the fingerprint below.
PROMPT_VERSION = 2


def load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


EXCERPT_CONTEXT = 2
EXCERPT_MAX_LINES = 60


def changed_excerpt(entry: dict) -> tuple[str, str]:
    """Before/after text for one article, centred on the lines that changed.

    Uses SequenceMatcher opcodes rather than matching diff lines by string
    equality: a sentence that appears twice in an article would otherwise mark
    an untouched copy as changed, and a pure insertion has no "-" line at all,
    so the old side fell back to an excerpt unrelated to the change. When the
    result still has to be trimmed, the prompt is told so explicitly instead of
    claiming the excerpt is the whole of the evidence.
    """
    before, after = entry["lines_before"], entry["lines_after"]
    if not before and not after:
        return "(なし)", "(なし)"

    keep_b: set[int] = set()
    keep_a: set[int] = set()
    for tag, i1, i2, j1, j2 in SequenceMatcher(
        a=before, b=after, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        keep_b |= set(range(max(0, i1 - EXCERPT_CONTEXT),
                            min(len(before), i2 + EXCERPT_CONTEXT)))
        keep_a |= set(range(max(0, j1 - EXCERPT_CONTEXT),
                            min(len(after), j2 + EXCERPT_CONTEXT)))

    def render(lines: list[str], keep: set[int]) -> str:
        if not lines:
            return "(なし)"
        if len(lines) <= EXCERPT_MAX_LINES:
            return "\n".join(lines)
        chosen = sorted(keep) or list(range(min(len(lines), EXCERPT_MAX_LINES)))
        trimmed = len(chosen) > EXCERPT_MAX_LINES
        chosen = chosen[:EXCERPT_MAX_LINES]
        out, prev = [], None
        for i in chosen:
            if prev is not None and i != prev + 1:
                out.append("…")
            out.append(lines[i])
            prev = i
        if trimmed:
            out.append("…（変更箇所が多いため一部のみ。ここに無い変更もある）")
        return "\n".join(out)

    return render(before, keep_b), render(after, keep_a)


def build_pr_summary_prompt(data: dict) -> str:
    """Build prompt for generating PR-style summary."""
    # 附則 used to be dropped here as "merely procedural". That was wrong twice
    # over: some amendments change nothing BUT the 附則 (労働基準法附則第138条,
    # the 中小企業 overtime-premium exemption, is the substance of its own
    # amendment), and dropping it left the prompt empty, so the model wrote the
    # summary from memory instead of from the diff. 附則 is now included and
    # labelled, and an empty grounds list is a hard error.
    changed_articles = []
    for d in data["diffs"]:
        title = d.get("title_after") or d.get("title_before") or ""
        change_type = {"added": "追加", "modified": "変更", "deleted": "削除"}[d["type"]]

        # The first 10 lines are not the change. When an article is long and
        # the amended sentence sits further down, a head-slice hands the model
        # an unchanged excerpt while the prompt below calls it "the whole of
        # the evidence" — which is an invitation to fill the gap from memory.
        before_text, after_text = changed_excerpt(d)

        if d.get("is_suppl"):
            where = f"附則（改正法 {d.get('amend_law_num') or '制定時'}）"
        else:
            where = " > ".join(d["section_path"]) if d["section_path"] else "本則"

        changed_articles.append(
            f"【{change_type}】{title}\n"
            f"所在: {where}\n"
            f"旧: {before_text}\n"
            f"新: {after_text}\n"
        )

    if not changed_articles:
        raise ValueError(
            "no changed articles to summarise — refusing to ask the model to "
            "write a summary with no grounds"
        )

    articles_text = "\n---\n".join(changed_articles)
    main_count = sum(1 for d in data["diffs"] if not d.get("is_suppl"))
    suppl_count = len(data["diffs"]) - main_count
    scope_note = (
        f"この改正で変わったのは附則{suppl_count}件だけで、"
        "本則の条文は変わっていません。その事実を踏まえて書いてください。"
        if main_count == 0
        else f"本則{main_count}条・附則{suppl_count}件が変わっています。"
    )

    return f"""あなたは日本の法律の専門家であり、法律の改正内容を一般市民にわかりやすく説明する役割を担っています。

以下は「{data['law_title']}」の改正差分です（{data['date_before']} → {data['date_after']}）。
改正法令: {data['revision_after']['amendment_law_title']}

## 変更された条文（抜粋）

{articles_text}

## 前提

{scope_note}
上に挙げた条文が、この改正の根拠のすべてです。ここに書かれていない数値・期限・
制度名・因果関係を、記憶や一般知識から補って書かないでください。根拠から言えない
項目は、短くするか省いてください。

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

    if diff_entry.get("is_suppl"):
        amend = diff_entry.get("amend_law_num") or ""
        kind = (
            f"これは本則の条文ではなく、改正法（{amend}）の**附則**です。"
            "附則は本則とは独立に番号が振られるので、本則の第○条とは別のものです。"
            "本則の条文であるかのように説明しないでください。"
            "なお附則には施行期日や経過措置のほか、実体的な特例を定めるものもあります"
            "（例: 労働基準法附則第138条）。どちらであるかは条文の内容から判断し、"
            "手続規定だと決めつけないでください。"
        )
    else:
        kind = "これは本則の条文です。"

    return f"""あなたは日本の法律の専門家です。以下の条文変更を一般市民にわかりやすく説明してください。

法令: {law_title}
条文: {title}
所在: {section}
変更種別: {change_type}
種別: {kind}

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


def load_previous_annotations(file_name: str) -> dict:
    """Load the currently shipped diff file so unchanged articles keep their
    annotation instead of being regenerated (and re-paid for)."""
    prev_path = (
        Path(__file__).parent.parent / "frontend" / "public" / "data" / file_name
    )
    if not prev_path.exists():
        return {}
    try:
        prev = json.loads(prev_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return {d["article_num"]: d for d in prev.get("diffs", [])}


def fingerprint(prompt: str) -> str:
    """Identity of everything that decides an annotation's content.

    The prompt already contains the article text, the section path, the 本則/
    附則 kind and the cross-reference context, so hashing it covers every input
    at once. Model and prompt version are folded in because they change the
    answer without changing the prompt body.
    """
    payload = f"{MODEL}\x00{PROMPT_VERSION}\x00{prompt}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def validate_pr_summary(summary) -> list[str]:
    """Structural check for the amendment summary before it is written.

    It goes to the same shipped file as the annotations, and pr-summary.tsx
    maps over key_changes — a string there fails the static build.
    """
    if not isinstance(summary, dict):
        return [f"pr_summary is {type(summary).__name__}, not an object"]
    errors = []
    for key in ("title", "summary", "impact", "background"):
        value = summary.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} is missing or not a non-empty string")
    # Absent is not "empty": pr-summary.tsx maps over key_changes, so a missing
    # key reaches the static build as undefined.map and fails it.
    if "key_changes" not in summary:
        errors.append("key_changes is missing")
    else:
        changes = summary["key_changes"]
        if not isinstance(changes, list):
            errors.append("key_changes is not a list")
        else:
            for i, change in enumerate(changes):
                if not isinstance(change, dict):
                    errors.append(f"key_changes[{i}] is not an object")
                    continue
                for key in ("theme", "description"):
                    value = change.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"key_changes[{i}].{key} is missing or not a "
                            "non-empty string"
                        )
    return errors


def validate_annotation(annotation: dict) -> list[str]:
    """Structural check before an annotation is written or reused.

    complete_json only guarantees "parses as JSON". Without this, a
    cross_references that came back as a string is stored, cached forever by
    fingerprint, and then breaks .map() in the diff viewer.
    """
    if not isinstance(annotation, dict):
        return [f"annotation is {type(annotation).__name__}, not an object"]
    errors = []
    for key in ("plain_summary", "change_description"):
        value = annotation.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} is missing or not a non-empty string")
    refs = annotation.get("cross_references", [])
    if not isinstance(refs, list):
        errors.append("cross_references is not a list")
    else:
        for i, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"cross_references[{i}] is not an object")
                continue
            for key in ("ref", "article_num", "context"):
                if not isinstance(ref.get(key), str):
                    errors.append(f"cross_references[{i}].{key} is not a string")
    return errors


def annotation_is_usable(annotation: dict | None) -> bool:
    """Reject annotations that are present but broken.

    Truncated model output used to be stored as prose, so pages shipped raw
    JSON in change_description. Those must not be treated as a cache hit, or
    the damage becomes permanent: the article text never changes, so the entry
    would be reused forever.
    """
    if not annotation or validate_annotation(annotation):
        return False
    # Raw JSON that was stored as prose: the shape a truncated answer left
    # behind before the truncation guard existed.
    for key in ("plain_summary", "change_description"):
        value = annotation[key]
        # Both conditions together: prose that merely quotes a JSON fragment is
        # legitimate, but a value that *opens* as an object and carries a key
        # separator is the truncated-answer shape.
        if value.lstrip().startswith("{") and '":' in value:
            return False
    return True


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
    # 附則 is excluded: this context is looked up by 本則 article number, and a
    # 附則第四条 listed alongside 本則第四条 is exactly the confusion this whole
    # change is undoing.
    all_articles = {}
    for d in data["diffs"]:
        if d.get("is_suppl"):
            continue
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
    pr_summary = complete_json(client, MODEL, pr_prompt, max_tokens=4000)
    problems = validate_pr_summary(pr_summary)
    if problems:
        print("ERROR: pr_summary failed validation: " + "; ".join(problems))
        sys.exit(1)
    print(f"  Title: {pr_summary['title']}")

    # 2. Generate per-article annotations, reusing the ones whose text is unchanged
    previous = load_previous_annotations(diff_path.name)
    print(f"Annotating {len(data['diffs'])} articles...")
    annotations = {}
    failures: list[str] = []
    reused = 0
    for i, d in enumerate(data["diffs"]):
        num = d["article_num"]
        title = d.get("title_after") or d.get("title_before") or num

        prompt = build_article_annotation_prompt(d, data["law_title"], all_articles_text)
        fp = fingerprint(prompt)

        prev = previous.get(num) or {}
        prev_annotation = prev.get("annotation")
        # A matching fingerprint is the only reason to reuse. The text-equality
        # fallback that used to cover fingerprint-less entries kept 11 shipped
        # annotations whose change_description was a truncated JSON fragment
        # (Gate3): they were written under a different prompt by a model that
        # ran out of tokens, and nothing about the article text said so.
        if annotation_is_usable(prev_annotation) and prev_annotation.get("fingerprint") == fp:
            annotations[num] = prev_annotation
            reused += 1
            continue

        print(f"  [{i+1}/{len(data['diffs'])}] {title}")

        try:
            annotation = complete_json(client, MODEL, prompt, max_tokens=4000)
            problems = validate_annotation(annotation)
            if problems:
                raise ValueError("; ".join(problems))
        except (ValueError, json.JSONDecodeError) as e:
            # Storing the unparsable text as prose is what shipped raw JSON to
            # readers. Nothing is written on failure; re-run after fixing.
            print(f"    ERROR: could not generate a usable annotation for {title}: {e}")
            failures.append(num)
            continue
        annotation["fingerprint"] = fp
        annotations[num] = annotation

    # 3. Save annotated data
    data["pr_summary"] = pr_summary
    for d in data["diffs"]:
        num = d["article_num"]
        if num in annotations:
            d["annotation"] = annotations[num]

    print(
        f"  reused {reused} existing annotations, "
        f"generated {len(data['diffs']) - reused - len(failures)}"
    )
    if failures:
        # Writing a file with holes in it looks like success on the next run,
        # because a missing annotation is indistinguishable from one that was
        # never needed. Fail the run instead and keep the shipped file as it is.
        print(f"  FAILED for {len(failures)} article(s): {', '.join(failures)}")
        sys.exit(1)

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
