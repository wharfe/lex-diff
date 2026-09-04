"""Regression tests for 附則 (SupplProvision) handling in diff.py.

e-Gov numbers 附則 articles 1, 2, 3... independently of the main provisions.
A flat map keyed by Num therefore lets 附則第一条 overwrite 本則第一条 — which
is exactly what happened before this fix (see issue #10).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from diff import compute_diff, find_articles, find_section_path, suppl_key


def article(num, text, caption=""):
    children = [{"tag": "ArticleTitle", "children": [f"第{num}条"]}]
    if caption:
        children.append({"tag": "ArticleCaption", "children": [caption]})
    children.append(
        {
            "tag": "Paragraph",
            "attr": {"Num": "1"},
            "children": [{"tag": "ParagraphSentence", "children": [text]}],
        }
    )
    return {"tag": "Article", "attr": {"Num": str(num)}, "children": children}


def law(main_articles, suppl_blocks=()):
    """Build a minimal Law tree: MainProvision + zero or more SupplProvision."""
    body = [{"tag": "MainProvision", "children": list(main_articles)}]
    for amend_num, arts in suppl_blocks:
        body.append(
            {
                "tag": "SupplProvision",
                "attr": {"AmendLawNum": amend_num},
                "children": list(arts),
            }
        )
    return {"tag": "Law", "children": [{"tag": "LawBody", "children": body}]}


def test_suppl_article_does_not_overwrite_main_article():
    tree = law(
        [article(1, "この法律は、日本国内において罪を犯したすべての者に適用する。")],
        [("令和五年法律第六六号", [article(1, "この法律は、公布の日から起算して二十日を経過した日から施行する。")])],
    )
    by_num = {a["num"]: a for a in find_articles(tree)}

    # 本則第一条 keeps its own text even though 附則第一条 comes later in the tree
    assert "日本国内において罪を犯した" in by_num["1"]["paragraphs"][0]["text"]
    assert by_num["1"]["is_suppl"] is False

    # 附則 lives in its own number space, tagged with the amending law
    key = suppl_key("令和五年法律第六六号", "1")
    assert key in by_num
    assert "公布の日から起算して" in by_num[key]["paragraphs"][0]["text"]
    assert by_num[key]["is_suppl"] is True
    assert by_num[key]["amend_law_num"] == "令和五年法律第六六号"


def test_multiple_suppl_blocks_do_not_collide():
    tree = law(
        [article(1, "本則第一条")],
        [
            ("令和四年法律第一号", [article(1, "旧附則第一条")]),
            ("令和五年法律第二号", [article(1, "新附則第一条")]),
        ],
    )
    nums = [a["num"] for a in find_articles(tree)]
    assert nums == [
        "1",
        suppl_key("令和四年法律第一号", "1"),
        suppl_key("令和五年法律第二号", "1"),
    ]


def test_main_article_change_is_not_masked_by_identical_suppl():
    """The bug's other half: a real 本則 change was swallowed when the 附則
    that overwrote it happened to be identical across the two versions."""
    suppl = ("令和五年法律第六六号", [article(1, "施行期日は変わらない。")])
    before = law([article(1, "改正前の本則第一条")], [suppl])
    after = law([article(1, "改正後の本則第一条")], [suppl])

    diffs = compute_diff(find_articles(before), find_articles(after))
    changed = {d["article_num"]: d for d in diffs}

    assert "1" in changed, "本則第一条の改正が附則に隠されている"
    assert changed["1"]["type"] == "modified"
    assert changed["1"]["is_suppl"] is False
    # the unchanged 附則 produces no diff entry of its own
    assert suppl_key("令和五年法律第六六号", "1") not in changed


def test_section_path_is_not_resolved_from_inside_suppl():
    tree = law(
        [
            {
                "tag": "Chapter",
                "children": [
                    {"tag": "ChapterTitle", "children": ["第一章　通則"]},
                    article(1, "本則第一条"),
                ],
            }
        ],
        [("令和五年法律第六六号", [article(1, "附則第一条")])],
    )
    assert find_section_path(tree, "1") == ["第一章　通則"]
    # 附則 keys never match a raw Num, so no 本則 path is invented for them
    assert find_section_path(tree, suppl_key("令和五年法律第六六号", "1")) is None


def test_suppl_identity_survives_a_block_inserted_before_it():
    """e-Gov inserts 附則 blocks in promulgation order, not at the end.

    Keying by position made one unchanged 附則 look like a delete plus an add
    whenever an older amendment was slotted in ahead of it (observed on 民法,
    2026-03-31 -> 2026-04-01, issue #10).
    """
    older = ("令和六年五月二二日法律第三〇号", [article(1, "後から挿入された附則")])
    target = ("令和六年五月二四日法律第三三号", [article(1, "変わっていない附則")])

    before = law([article(100, "本則")], [target])
    after = law([article(100, "本則")], [older, target])

    diffs = compute_diff(find_articles(before), find_articles(after))
    by_num = {d["article_num"]: d for d in diffs}

    # the untouched 附則 keeps its identity: no diff entry at all
    assert suppl_key("令和六年五月二四日法律第三三号", "1") not in by_num
    # only the genuinely new block shows up, as an addition
    inserted = suppl_key("令和六年五月二二日法律第三〇号", "1")
    assert by_num[inserted]["type"] == "added"
    assert len(diffs) == 1


def test_enactment_suppl_without_amend_law_num_gets_a_stable_key():
    tree = law([article(1, "本則")], [(None, [article(1, "制定時の附則")])])
    by_num = {a["num"] for a in find_articles(tree)}
    assert suppl_key(None, "1") in by_num


def suppl_block(amend_num, paragraph_texts, label="附　則"):
    """A SupplProvision with no Article children — a label plus bare Paragraphs.

    About a third of the 附則 blocks in the real e-Gov data have this shape.
    """
    children = [{"tag": "SupplProvisionLabel", "children": [label]}]
    for i, text in enumerate(paragraph_texts, start=1):
        children.append({
            "tag": "Paragraph",
            "attr": {"Num": str(i)},
            "children": [{"tag": "ParagraphSentence", "children": [text]}],
        })
    return {
        "tag": "SupplProvision",
        "attr": {"AmendLawNum": amend_num} if amend_num else {},
        "children": children,
    }


def law_with_blocks(main_articles, blocks):
    body = [{"tag": "MainProvision", "children": list(main_articles)}]
    body.extend(blocks)
    return {"tag": "Law", "children": [{"tag": "LawBody", "children": body}]}


def test_suppl_block_without_articles_is_not_dropped():
    tree = law_with_blocks(
        [article(1, "本則第一条")],
        [suppl_block("昭和三七年六月二日法律第一四七号",
                     ["この法律は、公布の日から施行する。", "経過措置は政令で定める。"])],
    )
    by_num = {a["num"]: a for a in find_articles(tree)}
    key = suppl_key("昭和三七年六月二日法律第一四七号", "本文")
    assert key in by_num, "Paragraph だけの附則ブロックが落ちている"
    entry = by_num[key]
    assert entry["is_suppl"] is True
    assert len(entry["paragraphs"]) == 2
    assert "公布の日から施行する" in entry["paragraphs"][0]["text"]
    # 本則 is untouched by the block
    assert "本則第一条" in by_num["1"]["paragraphs"][0]["text"]


def test_change_inside_an_article_less_suppl_block_shows_up_as_a_diff():
    amend = "令和六年五月二四日法律第三四号"
    before = law_with_blocks([article(1, "本則")], [suppl_block(amend, ["一年を超えない範囲内において政令で定める日から施行する。"])])
    after = law_with_blocks([article(1, "本則")], [suppl_block(amend, ["二年を超えない範囲内において政令で定める日から施行する。"])])

    diffs = compute_diff(find_articles(before), find_articles(after))
    assert len(diffs) == 1, "附則ブロック内の変更が差分に出ていない"
    assert diffs[0]["article_num"] == suppl_key(amend, "本文")
    assert diffs[0]["type"] == "modified"
    assert diffs[0]["is_suppl"] is True


def test_article_bearing_suppl_block_still_uses_article_numbers():
    """The new block path must not swallow blocks that do have Articles."""
    tree = law_with_blocks(
        [article(1, "本則")],
        [{"tag": "SupplProvision", "attr": {"AmendLawNum": "令和五年法律第六六号"},
          "children": [{"tag": "SupplProvisionLabel", "children": ["附　則"]},
                       article(1, "附則第一条")]}],
    )
    nums = {a["num"] for a in find_articles(tree)}
    assert suppl_key("令和五年法律第六六号", "1") in nums
    assert suppl_key("令和五年法律第六六号", "本文") not in nums


def test_suppl_block_with_articles_under_a_chapter_is_not_swallowed():
    """The law XML schema allows SupplProvision > Chapter > Article.

    A direct-child test for Article sent such a block down the article-less
    path and dropped every 条 in it. No current snapshot has this shape, which
    is why it has to be handled structurally rather than by observation.
    """
    chapter = {
        "tag": "Chapter",
        "children": [
            {"tag": "ChapterTitle", "children": ["第一章　経過措置"]},
            article(1, "附則第一条（章の下）"),
            article(2, "附則第二条（章の下）"),
        ],
    }
    tree = law_with_blocks(
        [article(1, "本則第一条")],
        [{"tag": "SupplProvision", "attr": {"AmendLawNum": "令和五年法律第六六号"},
          "children": [{"tag": "SupplProvisionLabel", "children": ["附　則"]}, chapter]}],
    )
    by_num = {a["num"]: a for a in find_articles(tree)}

    assert suppl_key("令和五年法律第六六号", "1") in by_num, "章の下の附則条文が落ちている"
    assert suppl_key("令和五年法律第六六号", "2") in by_num
    # not collapsed into a single block entry
    assert suppl_key("令和五年法律第六六号", "本文") not in by_num
    # 本則 keeps its own key
    assert "本則第一条" in by_num["1"]["paragraphs"][0]["text"]


def test_paragraph_only_block_collects_paragraphs_nested_in_a_container():
    """Mirror case: no Article anywhere, but the Paragraphs sit under a wrapper."""
    tree = law_with_blocks(
        [article(1, "本則")],
        [{"tag": "SupplProvision", "attr": {"AmendLawNum": "昭和四〇年法律第一号"},
          "children": [
              {"tag": "SupplProvisionLabel", "children": ["附　則"]},
              {"tag": "Chapter", "children": [
                  {"tag": "Paragraph", "attr": {"Num": "1"},
                   "children": [{"tag": "ParagraphSentence", "children": ["公布の日から施行する。"]}]},
              ]},
          ]}],
    )
    by_num = {a["num"]: a for a in find_articles(tree)}
    key = suppl_key("昭和四〇年法律第一号", "本文")
    assert key in by_num
    assert "公布の日から施行する" in by_num[key]["paragraphs"][0]["text"]


def test_bare_paragraphs_beside_articles_are_not_dropped():
    """The law XML schema allows Article and Paragraph as siblings under
    SupplProvision. Treating "has an Article" as "is entirely Articles" left
    the bare 項 — typically the 施行期日 — out of the diff entirely.
    """
    amend = "令和五年法律第六六号"
    tree = law_with_blocks(
        [article(1, "本則第一条")],
        [{"tag": "SupplProvision", "attr": {"AmendLawNum": amend},
          "children": [
              {"tag": "SupplProvisionLabel", "children": ["附　則"]},
              {"tag": "Paragraph", "attr": {"Num": "1"},
               "children": [{"tag": "ParagraphSentence",
                             "children": ["この法律は、公布の日から施行する。"]}]},
              article(2, "附則第二条"),
          ]}],
    )
    by_num = {a["num"]: a for a in find_articles(tree)}

    # the Article keeps its own key
    assert suppl_key(amend, "2") in by_num
    # and the bare 項 is not lost
    block = by_num.get(suppl_key(amend, "本文"))
    assert block is not None, "条と兄弟の裸の項が落ちている"
    assert "公布の日から施行する" in block["paragraphs"][0]["text"]
    assert "条以外の項" in block["title"]


def test_paragraphs_inside_an_article_are_not_pulled_into_the_block_entry():
    amend = "令和五年法律第六六号"
    tree = law_with_blocks(
        [article(1, "本則")],
        [{"tag": "SupplProvision", "attr": {"AmendLawNum": amend},
          "children": [
              {"tag": "SupplProvisionLabel", "children": ["附　則"]},
              {"tag": "Paragraph", "attr": {"Num": "1"},
               "children": [{"tag": "ParagraphSentence", "children": ["裸の項"]}]},
              article(2, "条の中の項"),
          ]}],
    )
    by_num = {a["num"]: a for a in find_articles(tree)}
    block = by_num[suppl_key(amend, "本文")]
    texts = " ".join(p["text"] for p in block["paragraphs"])
    assert "裸の項" in texts
    assert "条の中の項" not in texts, "Article 配下の項まで吸い込んでいる"
