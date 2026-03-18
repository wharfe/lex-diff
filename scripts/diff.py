"""Compute structural diff between two versions of a law.

Usage:
    python scripts/diff.py <law_id> <date_before> <date_after>

Example:
    python scripts/diff.py 129AC0000000089 2024-03-31 2024-04-01
"""

import sys
import json
from pathlib import Path
from difflib import unified_diff

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
DIFF_DIR = DATA_DIR / "diffs"


def extract_text(node: dict | str) -> str:
    """Recursively extract plain text from a law XML node."""
    if isinstance(node, str):
        return node
    return "".join(extract_text(c) for c in node.get("children", []))


def find_articles(node: dict | str) -> list[dict]:
    """Find all Article nodes and return structured data."""
    if isinstance(node, str):
        return []
    tag = node.get("tag", "")
    attr = node.get("attr", {})
    results = []

    if tag == "Article":
        num = attr.get("Num", "")
        title = ""
        paragraphs = []

        for child in node.get("children", []):
            if isinstance(child, str):
                continue
            child_tag = child.get("tag", "")
            if child_tag == "ArticleTitle":
                title = extract_text(child).strip()
            elif child_tag == "ArticleCaption":
                caption = extract_text(child).strip()
                if caption:
                    title = f"{title} {caption}".strip()
            elif child_tag == "Paragraph":
                para_num = child.get("attr", {}).get("Num", "")
                para_text = format_paragraph(child)
                paragraphs.append({"num": para_num, "text": para_text})

        results.append({
            "num": num,
            "title": title,
            "paragraphs": paragraphs,
        })

    for child in node.get("children", []):
        if isinstance(child, dict):
            results.extend(find_articles(child))

    return results


def format_paragraph(node: dict) -> str:
    """Format a Paragraph node into readable text."""
    parts = []
    for child in node.get("children", []):
        if isinstance(child, str):
            parts.append(child)
            continue
        tag = child.get("tag", "")
        if tag == "ParagraphNum":
            continue  # Skip paragraph numbers in text
        if tag == "ParagraphSentence":
            parts.append(extract_text(child).strip())
        elif tag == "Item":
            item_text = format_item(child, indent=1)
            parts.append(item_text)
        elif tag == "TableStruct":
            parts.append("[表]")
        else:
            text = extract_text(child).strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def format_item(node: dict, indent: int = 1) -> str:
    """Format an Item node with proper indentation."""
    prefix = "　" * indent
    parts = []
    for child in node.get("children", []):
        if isinstance(child, str):
            parts.append(child)
            continue
        tag = child.get("tag", "")
        if tag in ("ItemTitle", "ItemSentence"):
            parts.append(prefix + extract_text(child).strip())
        elif tag.startswith("Subitem"):
            parts.append(format_item(child, indent + 1))
        else:
            text = extract_text(child).strip()
            if text:
                parts.append(prefix + text)
    return "\n".join(parts)


def article_to_lines(article: dict) -> list[str]:
    """Convert an article to lines for diff comparison."""
    lines = [article["title"]]
    for para in article["paragraphs"]:
        for line in para["text"].split("\n"):
            if line.strip():
                lines.append(line)
    return lines


def compute_diff(before_articles: list[dict], after_articles: list[dict]) -> list[dict]:
    """Compute article-level diff between two versions."""
    before_map = {a["num"]: a for a in before_articles}
    after_map = {a["num"]: a for a in after_articles}

    all_nums = []
    seen = set()
    for a in before_articles:
        if a["num"] not in seen:
            all_nums.append(a["num"])
            seen.add(a["num"])
    for a in after_articles:
        if a["num"] not in seen:
            all_nums.append(a["num"])
            seen.add(a["num"])

    diffs = []

    for num in all_nums:
        old = before_map.get(num)
        new = after_map.get(num)

        if old and new:
            old_lines = article_to_lines(old)
            new_lines = article_to_lines(new)
            if old_lines == new_lines:
                continue  # No change

            diff_lines = list(unified_diff(
                old_lines, new_lines,
                fromfile=f"旧 {old['title']}",
                tofile=f"新 {new['title']}",
                lineterm="",
            ))

            diffs.append({
                "type": "modified",
                "article_num": num,
                "title_before": old["title"],
                "title_after": new["title"],
                "lines_before": old_lines,
                "lines_after": new_lines,
                "diff": diff_lines,
                "paragraphs_before": old["paragraphs"],
                "paragraphs_after": new["paragraphs"],
            })

        elif old and not new:
            diffs.append({
                "type": "deleted",
                "article_num": num,
                "title_before": old["title"],
                "title_after": None,
                "lines_before": article_to_lines(old),
                "lines_after": [],
                "diff": [f"-{line}" for line in article_to_lines(old)],
                "paragraphs_before": old["paragraphs"],
                "paragraphs_after": [],
            })

        elif not old and new:
            diffs.append({
                "type": "added",
                "article_num": num,
                "title_before": None,
                "title_after": new["title"],
                "lines_before": [],
                "lines_after": article_to_lines(new),
                "diff": [f"+{line}" for line in article_to_lines(new)],
                "paragraphs_before": [],
                "paragraphs_after": new["paragraphs"],
            })

    return diffs


def find_section_path(node: dict | str, article_num: str, path: list[str] | None = None) -> list[str] | None:
    """Find the section path (Part > Chapter > Section) for an article."""
    if path is None:
        path = []
    if isinstance(node, str):
        return None
    tag = node.get("tag", "")

    section_tags = {
        "Part": "PartTitle",
        "Chapter": "ChapterTitle",
        "Section": "SectionTitle",
        "Subsection": "SubsectionTitle",
    }

    current_path = path
    if tag in section_tags:
        title_tag = section_tags[tag]
        title = ""
        for c in node.get("children", []):
            if isinstance(c, dict) and c.get("tag") == title_tag:
                title = extract_text(c).strip()
        current_path = path + [title]

    if tag == "Article" and node.get("attr", {}).get("Num") == article_num:
        return current_path

    for c in node.get("children", []):
        if isinstance(c, dict):
            result = find_section_path(c, article_num, current_path)
            if result is not None:
                return result

    return None


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    law_id = sys.argv[1]
    date_before = sys.argv[2]
    date_after = sys.argv[3]

    before_path = RAW_DIR / f"{law_id}_{date_before}.json"
    after_path = RAW_DIR / f"{law_id}_{date_after}.json"

    if not before_path.exists() or not after_path.exists():
        print(f"Error: Run fetch.py first to download law data.")
        sys.exit(1)

    before_data = json.loads(before_path.read_text())
    after_data = json.loads(after_path.read_text())

    # Extract metadata
    law_title = before_data["revision_info"]["law_title"]
    before_revision = before_data["revision_info"]
    after_revision = after_data["revision_info"]

    print(f"Law: {law_title}")
    print(f"Before: {before_revision.get('amendment_law_title', 'original')} ({date_before})")
    print(f"After:  {after_revision.get('amendment_law_title', 'original')} ({date_after})")

    # Extract articles
    before_articles = find_articles(before_data["law_full_text"])
    after_articles = find_articles(after_data["law_full_text"])
    print(f"Articles: {len(before_articles)} -> {len(after_articles)}")

    # Compute diff
    diffs = compute_diff(before_articles, after_articles)
    print(f"Changed articles: {len(diffs)}")

    # Add section paths
    for d in diffs:
        num = d["article_num"]
        source = after_data if d["type"] != "deleted" else before_data
        section_path = find_section_path(source["law_full_text"], num)
        d["section_path"] = section_path or []

    # Build output
    stats = {
        "added": sum(1 for d in diffs if d["type"] == "added"),
        "modified": sum(1 for d in diffs if d["type"] == "modified"),
        "deleted": sum(1 for d in diffs if d["type"] == "deleted"),
    }

    output = {
        "law_id": law_id,
        "law_title": law_title,
        "date_before": date_before,
        "date_after": date_after,
        "revision_before": {
            "law_revision_id": before_revision.get("law_revision_id"),
            "amendment_law_title": before_revision.get("amendment_law_title"),
            "amendment_enforcement_date": before_revision.get("amendment_enforcement_date"),
        },
        "revision_after": {
            "law_revision_id": after_revision.get("law_revision_id"),
            "amendment_law_title": after_revision.get("amendment_law_title"),
            "amendment_enforcement_date": after_revision.get("amendment_enforcement_date"),
        },
        "stats": stats,
        "diffs": diffs,
    }

    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DIFF_DIR / f"{law_id}_{date_before}_{date_after}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nOutput: {out_path}")
    print(f"Stats: +{stats['added']} added, ~{stats['modified']} modified, -{stats['deleted']} deleted")


if __name__ == "__main__":
    main()
