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


# The 附則 a law was enacted with carries no AmendLawNum; every later block has
# one. Observed across all 34 raw snapshots: exactly one such block per law,
# always first, and AmendLawNum is unique within a law.
ORIGINAL_SUPPL = "原始"

# Suffix for a 附則 block that has no Article children — the block itself is the
# unit, so it needs a key that cannot collide with any Article Num.
SUPPL_BLOCK_BODY = "本文"


def subtree_has(node: dict, tag: str) -> bool:
    """True when `tag` appears anywhere under `node` (node itself excluded)."""
    for child in node.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        if child.get("tag") == tag or subtree_has(child, tag):
            return True
    return False


def walk_tags(
    node: dict, tags: set[str], stop_at: set[str] | None = None
) -> list[dict]:
    """Every descendant whose tag is in `tags`, in document order.

    `stop_at` prunes whole subtrees — used to collect the 項 that sit outside
    an Article without also swallowing the 項 that belong to one.
    """
    found = []
    for child in node.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        tag = child.get("tag")
        if stop_at and tag in stop_at:
            continue
        if tag in tags:
            found.append(child)
        else:
            found.extend(walk_tags(child, tags, stop_at))
    return found


def suppl_key(amend_law_num: str | None, num: str) -> str:
    """Namespaced key for a 附則 article.

    Keyed by the amending law rather than by position: e-Gov inserts blocks in
    promulgation order, not at the end, so a positional index shifts between
    versions and would turn one 附則 into a spurious deleted + added pair.
    """
    return f"suppl_{amend_law_num or ORIGINAL_SUPPL}_{num}"


def index_by_num(articles: list[dict]) -> dict[str, dict]:
    """Map article number -> article, refusing to let a duplicate win silently.

    This is the shape of issue #10 itself: a dict comprehension over articles
    keyed by Num let 附則第一条 overwrite 本則第一条, and the loss was invisible
    because the output still looked like a valid diff. The namespacing above
    makes a collision unlikely, not impossible — two SupplProvision blocks can
    still carry the same AmendLawNum, and a missing AmendLawNum falls back to
    the same ORIGINAL_SUPPL bucket. Fail loudly instead of dropping a 条文.
    """
    by_num: dict[str, dict] = {}
    for a in articles:
        num = a["num"]
        if not num:
            raise ValueError(f"article with empty Num: {a.get('title')!r}")
        if num in by_num:
            raise ValueError(
                f"duplicate article key {num!r} — one of these would be dropped: "
                f"{by_num[num].get('title')!r} vs {a.get('title')!r}"
            )
        by_num[num] = a
    return by_num


def find_articles(
    node: dict | str,
    in_suppl: bool = False,
    amend_law_num: str | None = None,
) -> list[dict]:
    """Find all Article nodes and return structured data.

    Articles inside SupplProvision (附則) are kept in a separate number space:
    e-Gov numbers them 1, 2, 3... independently of the main provisions, so a
    flat map keyed by Num lets 附則第一条 silently overwrite 本則第一条.
    """
    if isinstance(node, str):
        return []
    tag = node.get("tag", "")
    attr = node.get("attr", {})
    results = []

    if tag == "SupplProvision":
        in_suppl = True
        amend_law_num = attr.get("AmendLawNum")
        # About a third of 附則 blocks have no Article at all — just a label and
        # bare Paragraphs (558 of 1809 blocks across the 34 raw snapshots).
        # Collecting only Article nodes dropped those blocks entirely, so an
        # amendment that changed nothing else went out as an empty diff.
        # The whole block becomes one entry; its paragraphs are its body.
        #
        # The test is over the whole subtree, not the direct children: the law
        # XML schema allows SupplProvision > Chapter > Article, and a
        # direct-child test would send such a block down the article-less path
        # and drop every 条 in it. No snapshot has that shape today, which is
        # exactly why it has to be handled structurally rather than observed.
        # Paragraphs that are not inside an Article are collected either way.
        # The law XML schema allows Article and Paragraph as siblings under
        # SupplProvision; treating "has an Article" as "is entirely Articles"
        # dropped the bare 項 (施行期日 and the like) of such a block. No
        # snapshot has that shape today — which is exactly why round 2's
        # identical assumption survived until a reviewer pointed at the schema.
        if True:
            label = ""
            paragraphs = []
            for child in walk_tags(node, {"SupplProvisionLabel", "Paragraph"},
                                   stop_at={"Article"}):
                if child.get("tag") == "SupplProvisionLabel":
                    label = label or extract_text(child).strip()
                else:
                    paragraphs.append({
                        "num": child.get("attr", {}).get("Num", ""),
                        "text": format_paragraph(child),
                    })
            if paragraphs:
                title = label or "附則"
                if subtree_has(node, "Article"):
                    # The block also has 条; name this entry for what it is so
                    # it cannot be mistaken for the whole 附則.
                    title = f"{title}（条以外の項）"
                if amend_law_num:
                    title = f"{title}（{amend_law_num}）"
                results.append({
                    "num": suppl_key(amend_law_num, SUPPL_BLOCK_BODY),
                    "title": title,
                    "paragraphs": paragraphs,
                    "is_suppl": True,
                    "amend_law_num": amend_law_num,
                })
            if not subtree_has(node, "Article"):
                return results

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
            "num": suppl_key(amend_law_num, num) if in_suppl else num,
            "title": title,
            "paragraphs": paragraphs,
            "is_suppl": in_suppl,
            "amend_law_num": amend_law_num,
        })

    for child in node.get("children", []):
        if isinstance(child, dict):
            results.extend(find_articles(child, in_suppl, amend_law_num))

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
    before_map = index_by_num(before_articles)
    after_map = index_by_num(after_articles)

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
                "is_suppl": new.get("is_suppl", False),
                "amend_law_num": new.get("amend_law_num"),
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
                "is_suppl": old.get("is_suppl", False),
                "amend_law_num": old.get("amend_law_num"),
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
                "is_suppl": new.get("is_suppl", False),
                "amend_law_num": new.get("amend_law_num"),
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

    # 附則 has its own numbering; never resolve a 本則 path from inside it
    if tag == "SupplProvision":
        return None

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


def compute_stats(diffs: list[dict]) -> dict:
    """Change counts, with 本則 and 附則 kept apart.

    `added` / `modified` / `deleted` count 本則 only — the same numbers the site
    shows (frontend/lib/data.ts mainChangeCounts). They used to fold 附則 in,
    which made the published JSON claim "2 条が変更" for 労働基準法 2024 when the
    main text was untouched: e-Gov numbers each amending law's 附則 from 1
    independently, so they are a different axis, not more of the same articles.
    `suppl` carries how many 附則 entries there are; a per-type breakdown of
    them is deliberately not published — nothing reads it, and it is derivable
    from `diffs`, so it would be public surface with no reader.
    """
    main = [d for d in diffs if not d.get("is_suppl")]
    suppl = [d for d in diffs if d.get("is_suppl")]

    def count(entries: list[dict], type_: str) -> int:
        return sum(1 for d in entries if d["type"] == type_)

    return {
        "added": count(main, "added"),
        "modified": count(main, "modified"),
        "deleted": count(main, "deleted"),
        "main": len(main),
        "suppl": len(suppl),
    }


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

    # Compute diff. A key collision means one 条文 would be silently dropped —
    # the shape of issue #10 — so it stops this law rather than shipping a diff
    # with a hole in it. It is deliberately fatal for this law only: the caller
    # loops over laws, and the message names the colliding key.
    try:
        diffs = compute_diff(before_articles, after_articles)
    except ValueError as e:
        print(f"Error: {law_id} {date_before}->{date_after}: {e}")
        sys.exit(1)
    print(f"Changed articles: {len(diffs)}")

    # Add section paths
    for d in diffs:
        if d.get("is_suppl"):
            d["section_path"] = []
            continue
        num = d["article_num"]
        source = after_data if d["type"] != "deleted" else before_data
        section_path = find_section_path(source["law_full_text"], num)
        d["section_path"] = section_path or []

    # Build output
    stats = compute_stats(diffs)

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
    print(
        f"Stats (本則): +{stats['added']} added, ~{stats['modified']} modified, "
        f"-{stats['deleted']} deleted / 附則: {stats['suppl']}"
    )


if __name__ == "__main__":
    main()
