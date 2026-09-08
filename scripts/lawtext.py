"""Shared helpers for reading the e-Gov law XML-as-JSON tree.

Moved here from diff.py when law_summary.py needed the same two functions to
build its evidence. Keeping one copy is the same reason llm.py exists: the
three generator scripts drifted apart precisely because each held its own copy
of a helper. Nothing here knows about diffs or summaries — it is only the tree.
"""


def extract_text(node: dict | str) -> str:
    """Recursively extract plain text from a law XML node."""
    if isinstance(node, str):
        return node
    return "".join(extract_text(c) for c in node.get("children", []))


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
