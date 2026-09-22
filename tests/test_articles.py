# tests/test_articles.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import articles


@pytest.mark.parametrize(
    "num,slug",
    [("306", "306"), ("308_2", "308-2"), ("117_2_2", "117-2-2")],
)
def test_article_slug(num, slug):
    assert articles.article_slug(num) == slug


def test_article_slug_rejects_a_range_num():
    # 753:754 is e-Gov's element id for "第七百五十三条及び第七百五十四条", not an
    # article number. Nobody searches for it, and it must never become a URL.
    with pytest.raises(ValueError):
        articles.article_slug("753:754")


@pytest.mark.parametrize(
    "num,shown",
    [("306", "第306条"), ("308_2", "第308条の2"), ("117_2_2", "第117条の2の2")],
)
def test_display_num(num, shown):
    assert articles.display_num(num) == shown


def test_range_members():
    assert articles.range_members("753:754") == ["753", "754"]


def test_range_members_rejects_a_non_numeric_endpoint():
    with pytest.raises(ValueError):
        articles.range_members("753:754_2")


def _entry(num, type_="modified", suppl=False, **over):
    entry = {
        "type": type_,
        "article_num": num,
        "title_before": f"第{num}条",
        "title_after": f"第{num}条",
        "section_path": ["第二編　物権"],
        "paragraphs_before": [{"num": "1", "text": "旧"}],
        "paragraphs_after": [{"num": "1", "text": "新"}],
        "is_suppl": suppl,
        "annotation": {
            "plain_summary": f"{num} の説明",
            "change_description": f"{num} が変わった",
            "cross_references": [],
        },
    }
    entry.update(over)
    return entry


def _doc(date_after, entries, law_id="129AC0000000089", date_before="2026-03-31"):
    return {
        "law_id": law_id,
        "law_title": "民法",
        "date_before": date_before,
        "date_after": date_after,
        "revision_after": {"amendment_law_title": "民法等の一部を改正する法律"},
        "diffs": entries,
        "_diff_id": f"{law_id}_{date_before}_{date_after}",
    }


def test_suppl_entries_never_become_pages():
    changes = articles.collect_changes(
        [_doc("2026-04-01", [_entry("306"), _entry("1", suppl=True)])], "2026-09-22"
    )
    assert set(changes) == {"306"}


def test_unenforced_diffs_are_skipped():
    changes = articles.collect_changes(
        [_doc("2026-04-01", [_entry("306")]), _doc("2099-01-01", [_entry("999")])],
        "2026-09-22",
    )
    assert set(changes) == {"306"}


def test_changes_are_newest_first():
    docs = [
        _doc("2024-11-01", [_entry("117_2_2")]),
        _doc("2026-04-01", [_entry("117_2_2")]),
    ]
    dates = [c["enforcement_date"] for c in articles.collect_changes(docs, "2026-09-22")["117_2_2"]]
    assert dates == ["2026-04-01", "2024-11-01"]


def test_a_range_entry_is_dropped_when_its_members_have_their_own_entries():
    # 753:754 carries a plain_summary written about 754 only. Spreading it over
    # 753 would make that page claim 753 is about 夫婦間契約取消権.
    docs = [
        _doc(
            "2026-04-01",
            [
                _entry("753", "deleted"),
                _entry("754", "deleted"),
                _entry("753:754", "added"),
            ],
        )
    ]
    changes = articles.collect_changes(docs, "2026-09-22")
    assert set(changes) == {"753", "754"}
    assert all(c["type"] == "deleted" for cs in changes.values() for c in cs)


def test_a_range_entry_without_member_entries_raises():
    # Do not silently expand it. A range we do not already understand means the
    # law's structure is not what this script assumes.
    docs = [_doc("2026-04-01", [_entry("753:754", "added")])]
    with pytest.raises(ValueError, match="753:754"):
        articles.collect_changes(docs, "2026-09-22")


def _sentence(text):
    return {"tag": "Sentence", "attr": {}, "children": [text]}


def _article(num, label, caption=None, text="本文"):
    children = []
    if caption is not None:
        children.append({"tag": "ArticleCaption", "attr": {}, "children": [f"（{caption}）"]})
    children.append({"tag": "ArticleTitle", "attr": {}, "children": [label]})
    children.append(
        {
            "tag": "Paragraph",
            "attr": {},
            "children": [
                {"tag": "ParagraphNum", "attr": {}, "children": []},
                {"tag": "ParagraphSentence", "attr": {}, "children": [_sentence(text)]},
            ],
        }
    )
    return {"tag": "Article", "attr": {"Num": num}, "children": children}


def _tree(*arts):
    return {"tag": "Law", "attr": {}, "children": list(arts)}


def test_extract_article_body_keeps_caption_and_label_apart():
    # diff.find_articles overwrites the caption with the title; this must not.
    body = articles.extract_article_body(_article("306", "第三百六条", "一般の先取特権"))
    assert body["label"] == "第三百六条"
    assert body["caption"] == "一般の先取特権"
    assert body["paragraphs"][0]["text"] == "本文"


def test_a_caption_drops_its_ruby_reading():
    # 失踪 is marked up as <Ruby>踪<Rt>そう</Rt></Ruby>; extract_text would give
    # 失踪そうの宣告, which is not a phrase anyone types.
    ruby = {
        "tag": "ArticleCaption",
        "attr": {},
        "children": [
            "（失",
            {"tag": "Ruby", "attr": {}, "children": ["踪", {"tag": "Rt", "attr": {}, "children": ["そう"]}]},
            "の宣告）",
        ],
    }
    node = {"tag": "Article", "attr": {"Num": "30"}, "children": [ruby]}
    assert articles.extract_article_body(node)["caption"] == "失踪の宣告"


def test_paragraph_numbers_come_from_the_node_not_from_a_counter():
    # 民法772条 carries Paragraph@Num 1..4 with ParagraphNum "" ２ ３ ４
    # (measured). Renumbering by position loses the margin mark, and the first
    # paragraph's two sentences then read as two 項.
    def para(num, mark, text):
        children = []
        if mark:
            children.append({"tag": "ParagraphNum", "attr": {}, "children": [mark]})
        children.append(
            {"tag": "ParagraphSentence", "attr": {}, "children": [_sentence(text)]}
        )
        return {"tag": "Paragraph", "attr": {"Num": num}, "children": children}

    node = {
        "tag": "Article",
        "attr": {"Num": "772"},
        "children": [
            {"tag": "ArticleTitle", "attr": {}, "children": ["第七百七十二条"]},
            para("1", "", "妻が婚姻中に懐胎した子は…"),
            para("2", "２", "前項の場合において…"),
        ],
    }
    body = articles.extract_article_body(node)
    assert [p["num"] for p in body["paragraphs"]] == ["1", "2"]
    assert [p["mark"] for p in body["paragraphs"]] == ["", "２"]


def test_extract_article_body_without_a_caption():
    body = articles.extract_article_body(_article("754", "第七百五十四条"))
    assert body["caption"] == ""


def test_resolve_current_finds_an_exact_article():
    index = articles.index_current_articles(_tree(_article("306", "第三百六条", "一般の先取特権")))
    current = articles.resolve_current(index, "306", "modified")
    assert current["status"] == "present"
    assert current["source_article_num"] == "306"


def test_resolve_current_folds_a_deleted_article_into_its_merged_range():
    index = articles.index_current_articles(
        _tree(_article("753:754", "第七百五十三条及び第七百五十四条", text="削除"))
    )
    current = articles.resolve_current(index, "754", "deleted")
    assert current["status"] == "merged_deleted"
    assert current["source_article_num"] == "753:754"
    assert current["paragraphs"][0]["text"] == "削除"


def test_a_wide_range_whose_body_is_not_deleted_does_not_absorb_an_article():
    # A synthetic range with real text. Do NOT cite 育児介護休業法's 36:52 as the
    # example: measured 2026-09-22 its body is 削除 and Article_40 returns 400,
    # so it is a tombstone too (spec §6 carries the retraction). The rule stands
    # on the body being 削除, never on an example.
    index = articles.index_current_articles(
        _tree(_article("36:52", "第三十六条から第五十二条まで", text="実体のある本文"))
    )
    with pytest.raises(LookupError, match="40"):
        articles.resolve_current(index, "40", "deleted")


def test_resolve_current_raises_when_an_enforced_article_is_absent():
    index = articles.index_current_articles(_tree(_article("306", "第三百六条")))
    with pytest.raises(LookupError, match="999"):
        articles.resolve_current(index, "999", "modified")


def test_texts_match_ignores_trailing_whitespace_only():
    after = [{"num": "1", "text": "次に掲げる原因によって\n　一　共益の費用  "}]
    current = [{"num": "1", "text": "次に掲げる原因によって\n　一　共益の費用"}]
    assert articles.texts_match(after, current) is True


def test_texts_do_not_match_when_the_provision_was_renumbered():
    # 著作権法 122_2: the shipped note describes 秘密保持命令違反, today's text is
    # about 帳簿. Same number, different provision.
    after = [{"num": "1", "text": "秘密保持命令に違反した者は…"}]
    current = [{"num": "1", "text": "第百四条の二十七…に違反して帳簿を備えず…"}]
    assert articles.texts_match(after, current) is False


def test_texts_do_not_match_on_a_different_paragraph_count():
    assert articles.texts_match([{"num": "1", "text": "あ"}], []) is False


def test_texts_do_not_match_when_only_the_paragraph_numbers_differ():
    after = [{"num": "1", "text": "あ"}, {"num": "2", "text": "い"}]
    current = [{"num": "1", "text": "あ"}, {"num": "3", "text": "い"}]
    assert articles.texts_match(after, current) is False


def test_summary_with_an_abolished_penalty_absent_from_the_text_is_unsafe():
    # 刑法183: body says 拘禁刑, the 2023 note says 懲役 in the present tense.
    assert (
        articles.summary_is_safe("3年以下の懲役に処する条文", "三年以下の拘禁刑又は…")
        is False
    )


def test_summary_naming_a_penalty_that_is_still_in_the_text_is_safe():
    # A note about the amendment that renamed it is legitimate where the word
    # is still on the page.
    assert articles.summary_is_safe("懲役から拘禁刑に変わった", "…懲役…") is True


@pytest.mark.parametrize("term", ["懲役", "禁錮", "禁固", "禁こ"])
def test_every_abolished_penalty_spelling_is_checked(term):
    assert articles.summary_is_safe(f"{term}に処する", "拘禁刑に処する") is False
