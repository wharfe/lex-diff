"""changed_excerpt() must not hand the model an excerpt that omits the change.

The prompt tells the model the excerpt is the whole of the evidence, so a
silently dropped change invites it to fill the gap from memory — the shape
that produced a fabricated 労働基準法 summary before this was fixed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from annotate import EXCERPT_MAX_LINES, changed_excerpt


def entry(before, after):
    return {"lines_before": before, "lines_after": after, "diff": []}


def test_change_late_in_a_long_article_is_still_in_the_excerpt():
    before = [f"第{i}項の本文" for i in range(EXCERPT_MAX_LINES + 40)]
    after = list(before)
    target = EXCERPT_MAX_LINES + 20
    after[target] = "ここが改正された項"

    b, a = changed_excerpt(entry(before, after))
    assert "ここが改正された項" in a, "変更行が抜粋から落ちている"
    assert before[target] in b, "変更前の対応行が抜粋から落ちている"


def test_repeated_sentence_does_not_mark_untouched_copies():
    """A sentence appearing twice used to make the untouched copy look changed."""
    dup = "同じ文言の項"
    before = [dup] + [f"埋め草{i}" for i in range(EXCERPT_MAX_LINES + 10)] + [dup]
    after = list(before)
    after[-1] = "書き換えられた項"

    b, a = changed_excerpt(entry(before, after))
    assert "書き換えられた項" in a
    assert "埋め草0" not in a, "先頭の同一文が変更箇所として拾われている"


def test_pure_insertion_into_a_long_article_keeps_the_old_side_aligned():
    before = [f"項{i}" for i in range(EXCERPT_MAX_LINES + 30)]
    after = list(before)
    after.insert(EXCERPT_MAX_LINES + 10, "新設された項")

    b, a = changed_excerpt(entry(before, after))
    assert "新設された項" in a
    # the before side must show the neighbourhood of the insertion, not line 0
    assert f"項{EXCERPT_MAX_LINES + 9}" in b


def test_short_article_is_sent_whole():
    before = ["第一項", "第二項"]
    after = ["第一項", "第二項（改正後）"]
    b, a = changed_excerpt(entry(before, after))
    assert b == "第一項\n第二項"
    assert a == "第一項\n第二項（改正後）"


def test_trimmed_excerpt_says_so():
    before = [f"項{i}" for i in range(EXCERPT_MAX_LINES * 3)]
    after = [f"改{i}" for i in range(EXCERPT_MAX_LINES * 3)]
    _, a = changed_excerpt(entry(before, after))
    assert "ここに無い変更もある" in a, "切り詰めたのに黙っている"


def test_deletion_and_addition_sides_render_none_markers():
    b, a = changed_excerpt(entry(["消える条文"], []))
    assert b == "消える条文"
    assert a == "(なし)"
