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
