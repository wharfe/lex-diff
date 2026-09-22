"""Build the per-article pages for /law/<lawId>/article/<slug>.

Two sources meet here and they are not the same age. The amendment history and
the plain-language notes come from the shipped diffs, which trail the real laws
by months. The current text is fetched in this same run. Putting them side by
side is what the page is for, and it is also where they can contradict each
other -- see texts_match() and the version gate it guards.
"""

import re

# e-Gov numbers an article of the main text as "306", a sub-article as "308_2"
# (第308条の2), and a merged pair as "753:754". Only the first two are article
# numbers; the third is an element id that no reader searches for.
_RANGE_SEP = ":"


def is_range_num(article_num: str) -> bool:
    return _RANGE_SEP in article_num


def range_members(article_num: str) -> list[str]:
    """The article numbers a merged range covers."""
    if not is_range_num(article_num):
        raise ValueError(f"not a range: {article_num!r}")
    parts = article_num.split(_RANGE_SEP)
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"unsupported range shape: {article_num!r}")
    start, end = int(parts[0]), int(parts[1])
    if end < start:
        raise ValueError(f"reversed range: {article_num!r}")
    return [str(n) for n in range(start, end + 1)]


def article_slug(article_num: str) -> str:
    """URL form of an article number.

    Hyphen rather than underscore: an underscore joins words for a search
    engine where a hyphen separates them, and the conversion is one-to-one
    because no article_num contains a hyphen.
    """
    if is_range_num(article_num):
        raise ValueError(f"a range has no slug: {article_num!r}")
    if not re.fullmatch(r"[0-9]+(_[0-9]+)*", article_num):
        raise ValueError(f"unsupported article_num: {article_num!r}")
    return article_num.replace("_", "-")


def display_num(article_num: str) -> str:
    """Japanese reading of an article number, for prose and <title>."""
    if is_range_num(article_num):
        raise ValueError(f"a range has no display form: {article_num!r}")
    head, *rest = article_num.split("_")
    return "第" + head + "条" + "".join("の" + r for r in rest)


def collect_changes(diff_docs: list[dict], today: str) -> dict[str, list[dict]]:
    """Article number -> its amendments, newest first.

    Drops 附則 (numbered independently of the main text), amendments not yet in
    force, and range entries whose members already have entries of their own.
    """
    by_num: dict[str, list[dict]] = {}
    for doc in diff_docs:
        if doc["date_after"] > today:
            continue
        main = [e for e in doc["diffs"] if not e.get("is_suppl")]
        individual = {e["article_num"] for e in main if not is_range_num(e["article_num"])}
        for entry in main:
            num = entry["article_num"]
            if is_range_num(num):
                members = range_members(num)
                if all(m in individual for m in members):
                    # The members speak for themselves, and with the right text.
                    continue
                raise ValueError(
                    f"range entry {num!r} in {doc['_diff_id']} has no individual "
                    f"entry for every member ({members}); refusing to spread one "
                    "annotation over articles it was not written about"
                )
            annotation = entry.get("annotation") or {}
            by_num.setdefault(num, []).append(
                {
                    "diff_id": doc["_diff_id"],
                    "enforcement_date": doc["date_after"],
                    "date_before": doc["date_before"],
                    "year": doc["date_after"][:4],
                    "type": entry["type"],
                    "amendment_law_title": doc["revision_after"]["amendment_law_title"],
                    "change_description": annotation.get("change_description", ""),
                    "plain_summary": annotation.get("plain_summary", ""),
                    "cross_references": annotation.get("cross_references", []),
                    "section_path": entry.get("section_path", []),
                    "paragraphs_before": entry.get("paragraphs_before", []),
                    "paragraphs_after": entry.get("paragraphs_after", []),
                    "title_before": entry.get("title_before"),
                }
            )
    for num in by_num:
        by_num[num].sort(key=lambda c: c["enforcement_date"], reverse=True)
    return by_num
