"""Build the per-article pages for /law/<lawId>/article/<slug>.

Two sources meet here and they are not the same age. The amendment history and
the plain-language notes come from the shipped diffs, which trail the real laws
by months. The current text is fetched in this same run. Putting them side by
side is what the page is for, and it is also where they can contradict each
other -- see texts_match() and the version gate it guards.
"""

import re

from lawtext import extract_text, walk_tags
from diff import format_paragraph, find_section_path

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


# 附則 is numbered independently of the main text, so it must never enter the
# index keyed by article number.
SKIP_SUBTREES = {"SupplProvision"}

# What e-Gov leaves behind where an article used to be.
_DELETED_BODY = {"削除"}


def _text_without_ruby(node) -> str:
    """extract_text, minus the reading gloss.

    e-Gov marks up rare kanji as <Ruby>踪<Rt>そう</Rt></Ruby>, and extract_text
    concatenates both, yielding 失踪そうの宣告. That is fine inside a paragraph
    the reader skims and wrong in a <title>.
    """
    if isinstance(node, str):
        return node
    if node.get("tag") == "Rt":
        return ""
    return "".join(_text_without_ruby(c) for c in node.get("children", []) or [])


def extract_article_body(node: dict) -> dict:
    """An Article node split into the three things a page shows separately.

    diff.find_articles concatenates the caption onto the title and then lets the
    ArticleTitle child overwrite the result, so the caption is lost there. The
    caption is the phrase readers actually type ("夫婦間の契約の取消権"), so it
    is read on its own here.
    """
    label = ""
    caption = ""
    paragraphs = []
    for child in node.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        tag = child.get("tag")
        if tag == "ArticleTitle":
            label = extract_text(child).strip()
        elif tag == "ArticleCaption":
            caption = _text_without_ruby(child).strip().strip("（）()")
        elif tag == "Paragraph":
            # Two different numbers live here and format_paragraph drops both.
            # Paragraph@Num is what a citation uses (民法772条第2項);
            # ParagraphNum is what the printed law puts in the margin -- empty
            # for the first paragraph, ２ ３ ４ after it. Renumbering by
            # position instead would hide 項 boundaries on the 107 shipped
            # entries with more than one, and 民法772条第1項 holds two sentences
            # that a reader would then count as two 項.
            attr_num = (child.get("attr") or {}).get("Num") or str(len(paragraphs) + 1)
            marks = walk_tags(child, {"ParagraphNum"})
            paragraphs.append(
                {
                    "num": attr_num,
                    "mark": extract_text(marks[0]).strip() if marks else "",
                    "text": format_paragraph(child),
                }
            )
    return {"label": label, "caption": caption, "paragraphs": paragraphs}


def index_current_articles(law_full_text: dict) -> dict[str, dict]:
    """Article@Num -> Article node, for the main text only."""
    index = {}
    for node in walk_tags(law_full_text, {"Article"}, stop_at=SKIP_SUBTREES):
        num = (node.get("attr") or {}).get("Num")
        if num:
            index[num] = node
    return index


def _body_is_only_deleted(body: dict) -> bool:
    joined = "".join(p["text"] for p in body["paragraphs"]).strip()
    return joined in _DELETED_BODY


def resolve_current(index: dict, article_num: str, latest_type: str) -> dict:
    """The article as it stands today, or an error.

    Never returns "the article is gone": an article we have an enforced diff for
    must be findable, or our reading of the law's structure is wrong and the run
    should stop rather than ship a page with no text.
    """
    node = index.get(article_num)
    if node is not None:
        body = extract_article_body(node)
        return {
            "status": "present",
            "source_article_num": article_num,
            "source_label": body["label"],
            "caption": body["caption"],
            "paragraphs": body["paragraphs"],
        }

    if latest_type == "deleted":
        for key, candidate in index.items():
            if not is_range_num(key) or article_num not in range_members(key):
                continue
            body = extract_article_body(candidate)
            if not _body_is_only_deleted(body):
                # A range node whose body is anything but 削除 is a drafting
                # device, not a tombstone. (Do not cite 育児介護休業法's 36:52
                # here: measured 2026-09-22, its body IS 削除 and Article_40
                # returns 400, so it is a tombstone too. The rule stands on the
                # body, not on an example.)
                continue
            return {
                "status": "merged_deleted",
                "source_article_num": key,
                "source_label": body["label"],
                "caption": body["caption"],
                "paragraphs": body["paragraphs"],
            }

    raise LookupError(
        f"article {article_num!r} has an enforced diff but is not in today's "
        "text, and no merged-deleted range accounts for it"
    )


# 禁固 is the newspaper spelling and 禁こ the kana one; a list holding only 禁錮
# lets the same claim through in a different dress.
ABOLISHED_PENALTIES = {"懲役", "禁錮", "禁固", "禁こ"}


def _normalise(text: str) -> str:
    # Line endings and per-line trailing spaces are formatting. Leading
    # indentation is not: diff.format_item indents with a full-width space,
    # so a leading space is part of the provision's structure. A whole-string
    # .strip() would eat that leading space too, so only rstrip each line.
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))


def texts_match(paragraphs_after: list[dict], current_paragraphs: list[dict]) -> bool:
    """Whether the note's article and today's article are the same text."""
    if not paragraphs_after or not current_paragraphs:
        # A gate must fail closed: an empty side (diff.py yields [] for a
        # deleted entry) must never compare equal to anything, including
        # another empty list.
        return False
    if len(paragraphs_after) != len(current_paragraphs):
        return False
    # num can come from different fallbacks on each side (diff.py:159 yields
    # "" when Paragraph@Num is missing; articles.py's index falls back to a
    # positional number instead), so the two sides are not guaranteed to
    # agree even for the same paragraph. When they disagree the comparison
    # below reports a mismatch, which is the safe direction here.
    return all(
        a.get("num") == b.get("num")
        and _normalise(a.get("text", "")) == _normalise(b.get("text", ""))
        for a, b in zip(paragraphs_after, current_paragraphs)
    )


def summary_is_safe(summary: str, current_text: str) -> bool:
    """False when prose names a penalty the article no longer carries.

    The 2025-06-01 merger into 拘禁刑 is the case this exists for: a note
    written before it says 懲役 in the present tense, and printing that beside a
    body that says 拘禁刑 is the accident CLAUDE.md records, in a new place.
    """
    return not any(
        term in summary and term not in current_text for term in ABOLISHED_PENALTIES
    )


def build_alias_table(pages: dict[str, dict]) -> dict[str, str]:
    """Japanese article label -> article_num, for this law only."""
    return {p["label"]: num for num, p in pages.items() if p.get("label")}


# An article number continues after の only with a numeral: 第七百七十八条の四
# is another article, 第七百七十八条の規定 is the same one.
# Kanji today; Arabic too, so that adding display_num ("第778条の4") to the
# alias table later cannot make 第778条の4 resolve to 第778条.
_KANJI_DIGITS = set("一二三四五六七八九十百千0123456789０１２３４５６７８９")


def _normalise_ref_num(raw: str) -> str:
    """The many shapes an LLM wrote an article number in, as one shape."""
    return raw.replace("-", "_").replace("の", "_").strip()


def resolve_cross_references(
    refs: list[dict], alias_to_num: dict[str, str], self_num: str
) -> tuple[list[dict], int]:
    """Decide which references may become links.

    The `article_num` these carry is free-form LLM output: it names other laws,
    it is sometimes empty, and it is written three different ways. So the label
    decides, and article_num only gets a veto.
    """
    resolved = []
    unresolved = 0
    for ref in refs:
        label = (ref.get("ref") or "").strip()
        target = None
        # A reference that opens with a law name is about another law. One that
        # mentions 附則 is about provisions this page set never covers.
        if label.startswith("第") and "附則" not in label:
            # Longest alias first: 民法 ships 778, 778_2, 778_3 and 778_4 at
            # once, and 第七百七十八条 is a prefix of 第七百七十八条の四.
            for alias in sorted(alias_to_num, key=len, reverse=True):
                if not label.startswith(alias):
                    continue
                # Even the longest match can be a prefix when the sub-article
                # itself has no page: 第七百七十八条の四 would otherwise link to
                # 第七百七十八条. "の" + a kanji numeral continues the number.
                rest = label[len(alias):]
                if rest[:1] == "の" and rest[1:2] in _KANJI_DIGITS:
                    break  # a sub-article we do not have a page for
                target = alias_to_num[alias]
                break
        if target == self_num:
            target = None
        raw_num = _normalise_ref_num(ref.get("article_num") or "")
        # "7782" is 778_2 with the separator missing, not a different article,
        # and 8 shipped references are written that way. "824" against 824_2 is
        # a different article and must still lose the link.
        if target is not None and raw_num and raw_num not in (target, target.replace("_", "")):
            # The two halves of the reference disagree. Do not guess.
            target = None
        if target is None:
            unresolved += 1
        resolved.append(
            {
                "ref": label,
                "article_num": ref.get("article_num", ""),
                "context": ref.get("context", ""),
                "slug": article_slug(target) if target else None,
                "has_page": target is not None,
            }
        )
    return resolved, unresolved
