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


def test_texts_do_not_match_when_both_sides_are_empty():
    # A gate must fail closed: diff.py yields [] for a deleted entry's
    # paragraphs_after, and that must never compare equal to anything.
    assert articles.texts_match([], []) is False


def test_texts_do_not_match_when_only_leading_indentation_differs():
    # diff.format_item indents with a full-width space; that indentation is
    # part of the provision's structure, not incidental formatting.
    after = [{"num": "1", "text": "　共益の費用"}]
    current = [{"num": "1", "text": "共益の費用"}]
    assert articles.texts_match(after, current) is False


# 民法は 778 / 778_2 / 778_3 / 778_4 を同時に持つ（実測）。短い条名が長い条名の
# 接頭辞になるので、別名表は必ずこの形でテストする。
ALIASES = {
    "第三百六条": "306",
    "第三百八条の二": "308_2",
    "第七百六十六条": "766",
    "第七百七十八条": "778",
    "第七百七十八条の四": "778_4",
}


def test_a_reference_to_another_law_is_not_linked():
    refs = [{"ref": "民法第八百十七条の二第一項", "article_num": "817-2", "context": "c"}]
    resolved, unresolved = articles.resolve_cross_references(refs, ALIASES, "2")
    assert resolved[0]["has_page"] is False
    assert resolved[0]["slug"] is None
    assert unresolved == 1


def test_a_reference_to_a_supplementary_provision_is_not_linked():
    refs = [{"ref": "附則第三条", "article_num": "3", "context": "c"}]
    resolved, _ = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["has_page"] is False


def test_a_same_law_reference_resolves_by_its_japanese_label():
    refs = [{"ref": "第三百八条の二", "article_num": "308_2", "context": "c"}]
    resolved, unresolved = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["has_page"] is True
    assert resolved[0]["slug"] == "308-2"
    assert unresolved == 0


def test_a_self_reference_is_not_linked():
    refs = [{"ref": "第三百六条", "article_num": "306", "context": "c"}]
    resolved, _ = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["has_page"] is False


def test_a_reference_whose_article_num_contradicts_its_label_is_not_linked():
    refs = [{"ref": "第三百八条の二", "article_num": "766", "context": "c"}]
    resolved, _ = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["has_page"] is False


def test_a_reference_with_an_empty_article_num_still_resolves_by_label():
    refs = [{"ref": "第七百六十六条に定める", "article_num": "", "context": "c"}]
    resolved, _ = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["has_page"] is True
    assert resolved[0]["slug"] == "766"


def test_a_longer_article_label_wins_over_its_own_prefix():
    # 民法 ships 778, 778_2, 778_3 and 778_4 together. First-match-wins makes
    # 第七百七十八条 swallow 第七百七十八条の四, and the article_num veto then
    # hides the damage by dropping the link entirely.
    refs = [{"ref": "第七百七十八条の四", "article_num": "778_4", "context": "c"}]
    resolved, unresolved = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["slug"] == "778-4"
    assert unresolved == 0


def test_a_prefix_label_still_resolves_to_itself():
    refs = [{"ref": "第七百七十八条に定める", "article_num": "778", "context": "c"}]
    resolved, _ = articles.resolve_cross_references(refs, ALIASES, "306")
    assert resolved[0]["slug"] == "778"


def test_a_sub_article_without_a_page_does_not_link_to_its_parent():
    # 第七百七十八条の四 is a different article from 第七百七十八条. When only the
    # parent has a page, the reference must not quietly point at it.
    aliases = {"第七百七十八条": "778"}
    refs = [{"ref": "第七百七十八条の四", "article_num": "778_4", "context": "c"}]
    resolved, unresolved = articles.resolve_cross_references(refs, aliases, "306")
    assert resolved[0]["has_page"] is False
    assert unresolved == 1


def test_a_reference_continuing_with_non_numeral_text_still_resolves():
    aliases = {"第七百七十八条": "778"}
    refs = [{"ref": "第七百七十八条の規定により", "article_num": "778", "context": "c"}]
    resolved, _ = articles.resolve_cross_references(refs, aliases, "306")
    assert resolved[0]["slug"] == "778"


def test_build_alias_table_maps_japanese_labels_to_numbers():
    pages = {"306": {"label": "第三百六条"}, "308_2": {"label": "第三百八条の二"}}
    assert articles.build_alias_table(pages) == {
        "第三百六条": "306",
        "第三百八条の二": "308_2",
    }


SOURCE = {
    "asof": "2026-09-22",
    "fetched_at": "2026-09-22T14:07:31+09:00",
    "law_revision_id": "129AC0000000089_20260624_508AC0000000045",
    "amendment_enforcement_date": "2026-06-24",
}


def _build(entries, tree, today="2026-09-22"):
    changes = articles.collect_changes([_doc("2026-04-01", entries)], today)
    return articles.build_law_articles("129AC0000000089", "民法", changes, tree, SOURCE)


def test_current_summary_is_kept_when_the_text_still_matches():
    entries = [_entry("306", paragraphs_after=[{"num": "1", "text": "本文"}])]
    doc = _build(entries, _tree(_article("306", "第三百六条", "一般の先取特権")))
    page = doc["articles"][0]
    assert page["current_summary"]["text"] == "306 の説明"
    assert page["current_summary"]["evidence_date"] == "2026-04-01"
    assert page["caption"] == "一般の先取特権"


def test_current_summary_is_dropped_when_the_text_has_moved_on():
    entries = [_entry("306", paragraphs_after=[{"num": "1", "text": "昔の本文"}])]
    doc = _build(entries, _tree(_article("306", "第三百六条", text="今日の本文")))
    assert doc["articles"][0]["current_summary"] is None


def test_the_dropped_summary_survives_on_its_history_card():
    entries = [_entry("306", paragraphs_after=[{"num": "1", "text": "昔の本文"}])]
    doc = _build(entries, _tree(_article("306", "第三百六条", text="今日の本文")))
    assert doc["articles"][0]["changes"][0]["plain_summary"] == "306 の説明"


def test_a_matching_text_with_an_abolished_penalty_still_loses_its_summary():
    entries = [
        _entry(
            "183",
            paragraphs_after=[{"num": "1", "text": "拘禁刑"}],
            annotation={
                "plain_summary": "3年以下の懲役に処する",
                "change_description": "d",
                "cross_references": [],
            },
        )
    ]
    doc = _build(entries, _tree(_article("183", "第百八十三条", text="拘禁刑")))
    assert doc["articles"][0]["current_summary"] is None


def test_a_deleted_article_keeps_the_text_it_had_before():
    # Real deleted entries carry paragraphs_after == [] (measured on 民法753/754),
    # so the gate can never match and current_summary is always None here.
    entries = [
        _entry("753", "deleted", paragraphs_after=[]),
        _entry(
            "754",
            "deleted",
            paragraphs_after=[],
            paragraphs_before=[{"num": "1", "text": "夫婦間でした契約は…"}],
        ),
        _entry("753:754", "added"),
    ]
    doc = _build(entries, _tree(_article("753:754", "第七百五十三条及び第七百五十四条", text="削除")))
    page = next(a for a in doc["articles"] if a["article_num"] == "754")
    assert page["current"]["status"] == "merged_deleted"
    assert page["former"]["paragraphs"][0]["text"] == "夫婦間でした契約は…"
    assert page["former"]["as_of"] == "2026-03-31"
    assert page["current_summary"] is None


def test_a_deleted_article_takes_its_section_path_from_the_range_it_folded_into():
    # find_section_path(tree, "754") is None today -- 754 is not an Article node
    # any more. The range that absorbed it still is.
    entries = [
        _entry("753", "deleted", paragraphs_after=[]),
        _entry("754", "deleted", paragraphs_after=[]),
        _entry("753:754", "added"),
    ]
    tree = {
        "tag": "Law",
        "attr": {},
        "children": [
            {
                "tag": "Chapter",
                "attr": {},
                "children": [
                    {"tag": "ChapterTitle", "attr": {}, "children": ["第二章　婚姻"]},
                    _article("753:754", "第七百五十三条及び第七百五十四条", text="削除"),
                ],
            }
        ],
    }
    doc = _build(entries, tree)
    page = next(a for a in doc["articles"] if a["article_num"] == "754")
    assert page["section_path"] == ["第二章　婚姻"]


def test_related_articles_are_empty_when_the_text_has_moved_on():
    # spec §4: the gate covers the whole "about this article" block. A link
    # written about an older version can point at an article that has moved.
    refs = [{"ref": "第七百六十六条", "article_num": "766", "context": "c"}]
    entries = [
        _entry(
            "306",
            paragraphs_after=[{"num": "1", "text": "昔の本文"}],
            annotation={"plain_summary": "s", "change_description": "d", "cross_references": refs},
        )
    ]
    doc = _build(entries, _tree(_article("306", "第三百六条", text="今日の本文")))
    page = doc["articles"][0]
    assert page["related_articles"] == []
    # but the card still carries them, as dated text
    assert page["changes"][0]["cross_references"][0]["ref"] == "第七百六十六条"


def test_articles_are_ordered_numerically_not_by_slug_string():
    # 刑法 ships 3, 3_2, 176..183, 241. Sorting slugs as strings puts 3 last,
    # and this order is the table of contents on /law/<lawId>.
    entries = [_entry(n, paragraphs_after=[{"num": "1", "text": "本文"}]) for n in ("241", "3", "176")]
    tree = _tree(
        _article("241", "第二百四十一条"),
        _article("3", "第三条"),
        _article("176", "第百七十六条"),
    )
    doc = _build(entries, tree)
    assert [a["article_num"] for a in doc["articles"]] == ["3", "176", "241"]


def test_validate_rejects_an_empty_current_text():
    doc = {"law_id": "x", "law_title": "y", "source": SOURCE, "articles": [
        {"article_num": "306", "slug": "306", "label": "第三百六条",
         "current": {"status": "present", "paragraphs": [{"num": "1", "text": "  "}]},
         "changes": [{"change_description": "d"}]}
    ]}
    assert any("empty" in e for e in articles.validate_articles(doc))


def test_validate_rejects_a_duplicate_slug():
    page = {"article_num": "306", "slug": "306", "label": "l",
            "current": {"status": "present", "paragraphs": [{"num": "1", "text": "t"}]},
            "changes": [{"change_description": "d"}]}
    doc = {"law_id": "x", "law_title": "y", "source": SOURCE, "articles": [page, dict(page)]}
    assert any("duplicate" in e for e in articles.validate_articles(doc))


def test_validate_rejects_an_enforcement_date_after_the_asof():
    source = dict(SOURCE, amendment_enforcement_date="2099-01-01")
    doc = {"law_id": "x", "law_title": "y", "source": source, "articles": [
        {"article_num": "306", "slug": "306", "label": "l",
         "current": {"status": "present", "paragraphs": [{"num": "1", "text": "t"}]},
         "changes": [{"change_description": "d"}]}
    ]}
    assert any("enforcement" in e for e in articles.validate_articles(doc))


def test_build_alias_table_drops_a_label_claimed_by_two_pages():
    # A deleted article's label comes from the range node that absorbed it,
    # so e.g. 民法 753 and 754 both carry "753:754"'s title. An ambiguous
    # alias must not resolve to either page.
    pages = {
        "753": {"label": "第七百五十三条及び第七百五十四条"},
        "754": {"label": "第七百五十三条及び第七百五十四条"},
        "306": {"label": "第三百六条"},
    }
    aliases = articles.build_alias_table(pages)
    assert "第七百五十三条及び第七百五十四条" not in aliases
    assert aliases == {"第三百六条": "306"}


def test_validate_rejects_a_merged_deleted_page_with_empty_former_paragraphs():
    doc = {"law_id": "x", "law_title": "y", "source": SOURCE, "articles": [
        {"article_num": "754", "slug": "754", "label": "l",
         "current": {"status": "merged_deleted", "paragraphs": [{"num": "1", "text": "t"}]},
         "former": {"as_of": "2026-03-31", "label": "l", "paragraphs": []},
         "changes": [{"change_description": "d"}]}
    ]}
    assert any("former text" in e for e in articles.validate_articles(doc))


def test_validate_rejects_a_slug_that_does_not_match_its_article_num():
    doc = {"law_id": "x", "law_title": "y", "source": SOURCE, "articles": [
        {"article_num": "306", "slug": "999", "label": "l",
         "current": {"status": "present", "paragraphs": [{"num": "1", "text": "t"}]},
         "changes": [{"change_description": "d"}]}
    ]}
    assert any("does not match article_num" in e for e in articles.validate_articles(doc))


def test_validate_reports_but_does_not_raise_on_a_range_shaped_article_num():
    doc = {"law_id": "x", "law_title": "y", "source": SOURCE, "articles": [
        {"article_num": "753:754", "slug": "753", "label": "l",
         "current": {"status": "present", "paragraphs": [{"num": "1", "text": "t"}]},
         "changes": [{"change_description": "d"}]}
    ]}
    # Must return a list of strings, never raise -- but a range-shaped
    # article_num should never reach here (collect_changes excludes ranges),
    # so its arrival must be reported, not silently skipped.
    errors = articles.validate_articles(doc)
    assert isinstance(errors, list)
    assert any("article_num is not in a form" in e for e in errors)


import datetime
import json

import httpx


def _law_document(tree=None):
    return {
        "law_full_text": tree or _tree(_article("306", "第三百六条", "一般の先取特権")),
        "revision_info": {
            "law_revision_id": "129AC0000000089_20260624_508AC0000000045",
            "amendment_enforcement_date": "2026-06-24",
            "law_title": "民法",
        },
    }


def _shipped_diff(tmp_path, entries=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "129AC0000000089_2026-03-31_2026-04-01.json"
    path.write_text(
        json.dumps(
            _doc("2026-04-01", entries or [_entry("306", paragraphs_after=[{"num": "1", "text": "本文"}])]),
            ensure_ascii=False,
        )
    )
    return path


def _prepare(monkeypatch, tmp_path, fetch):
    shipped = tmp_path / "frontend" / "public" / "data"
    _shipped_diff(shipped)
    monkeypatch.setattr(articles, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(articles, "FRONTEND_DIR", shipped)
    monkeypatch.setattr(articles, "fetch_law_data", fetch)
    monkeypatch.setattr(sys, "argv", ["articles.py", "--all"])
    return shipped


def _written(tmp_path):
    out = list((tmp_path / "frontend" / "public" / "data" / "articles").glob("*.json"))
    return out + list((tmp_path / "data" / "articles").glob("*.json"))


def test_main_exits_nonzero_and_saves_nothing_when_the_fetch_fails(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise httpx.HTTPError("e-Gov is down")

    _prepare(monkeypatch, tmp_path, boom)
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code != 0
    assert _written(tmp_path) == []


def test_main_saves_nothing_when_the_api_returns_no_law_full_text(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, lambda *a, **k: {"revision_info": {}})
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code != 0
    assert _written(tmp_path) == []


def test_main_saves_nothing_when_validation_fails(monkeypatch, tmp_path):
    # An article with no paragraphs at all: a truncated response.
    empty = _tree({"tag": "Article", "attr": {"Num": "306"}, "children": []})
    _prepare(monkeypatch, tmp_path, lambda *a, **k: _law_document(empty))
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 2
    assert _written(tmp_path) == []


def test_main_does_not_save_when_the_day_changes_mid_generation(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, lambda *a, **k: _law_document())
    real_now = datetime.datetime.now
    calls = []

    class Clock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(1)
            base = real_now(tz)
            return base if len(calls) == 1 else base + datetime.timedelta(days=1)

    monkeypatch.setattr(articles.datetime, "datetime", Clock)
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 3
    assert _written(tmp_path) == []


def test_main_writes_both_copies_on_success(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, lambda *a, **k: _law_document())
    articles.main()
    assert (tmp_path / "frontend" / "public" / "data" / "articles" / "129AC0000000089.json").exists()
    assert (tmp_path / "data" / "articles" / "129AC0000000089.json").exists()


def test_the_law_title_comes_from_todays_revision_not_the_shipped_diff(monkeypatch, tmp_path):
    # 413AC0000000137 was renamed. The shipped diff keeps the old name; a page
    # headed "current text as of today" must not.
    renamed = _law_document()
    renamed["revision_info"]["law_title"] = "新しい名前の法律"
    _prepare(monkeypatch, tmp_path, lambda *a, **k: renamed)
    articles.main()
    doc = json.loads(
        (tmp_path / "frontend" / "public" / "data" / "articles" / "129AC0000000089.json").read_text()
    )
    assert doc["law_title"] == "新しい名前の法律"


def test_main_fails_when_the_revision_carries_no_law_title(monkeypatch, tmp_path):
    nameless = _law_document()
    nameless["revision_info"].pop("law_title", None)
    _prepare(monkeypatch, tmp_path, lambda *a, **k: nameless)
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 4
    assert _written(tmp_path) == []


def test_no_law_is_published_when_a_later_law_fails_validation(monkeypatch, tmp_path):
    # The all-or-nothing promise is only tested by a run where an earlier law
    # already succeeded. One law proves nothing about it.
    shipped = tmp_path / "frontend" / "public" / "data"
    _shipped_diff(shipped)
    (shipped / "140AC0000000045_2023-07-12_2023-07-13.json").write_text(
        json.dumps(
            _doc("2023-07-13", [_entry("183", paragraphs_after=[{"num": "1", "text": "本文"}])],
                 law_id="140AC0000000045", date_before="2023-07-12"),
            ensure_ascii=False,
        )
    )

    def fetch(law_id, asof):
        if law_id == "140AC0000000045":
            # An article that is present but empty: a truncated response.
            return _law_document(_tree({"tag": "Article", "attr": {"Num": "183"}, "children": []}))
        return _law_document()

    monkeypatch.setattr(articles, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(articles, "FRONTEND_DIR", shipped)
    monkeypatch.setattr(articles, "fetch_law_data", fetch)
    monkeypatch.setattr(sys, "argv", ["articles.py", "--all"])

    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 2
    # 129AC... was built successfully before 140AC... failed. Neither ships.
    assert _written(tmp_path) == []


def test_a_stale_articles_file_is_removed_when_the_law_drops_out(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, lambda *a, **k: _law_document())
    stale = tmp_path / "frontend" / "public" / "data" / "articles" / "999AC0000000001.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}")
    articles.main()
    assert not stale.exists()


def test_a_law_with_no_main_text_change_is_a_success_with_no_file(monkeypatch, tmp_path):
    # 労働基準法 ships only 附則 changes. This must not be an error.
    shipped = tmp_path / "frontend" / "public" / "data"
    shipped.mkdir(parents=True)
    (shipped / "322AC0000000049_2024-05-30_2024-05-31.json").write_text(
        json.dumps(_doc("2024-05-31", [_entry("1", suppl=True)], law_id="322AC0000000049"),
                   ensure_ascii=False)
    )
    monkeypatch.setattr(articles, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(articles, "FRONTEND_DIR", shipped)
    monkeypatch.setattr(articles, "fetch_law_data", lambda *a, **k: _law_document())
    monkeypatch.setattr(sys, "argv", ["articles.py", "--all"])
    articles.main()
    assert _written(tmp_path) == []


def test_an_unrecognized_flag_exits_without_touching_shipped_data(monkeypatch, tmp_path):
    # A dropped, unrecognised flag used to fall through to "no explicit law
    # ids" -- a full run, which ends by deleting every unmatched
    # articles/*.json. `--dry-run` must not be able to delete shipped data.
    _prepare(monkeypatch, tmp_path, lambda *a, **k: _law_document())
    stale = tmp_path / "frontend" / "public" / "data" / "articles" / "999AC0000000001.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}")
    monkeypatch.setattr(sys, "argv", ["articles.py", "--dry-run"])
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 5
    assert stale.exists()


def test_an_explicit_law_id_with_no_shipped_diff_fails_the_run(monkeypatch, tmp_path):
    # A typo'd law id ("129ac..." for "129AC...") used to print "skipping"
    # and exit 0, so a broken CI invocation would go green.
    _prepare(monkeypatch, tmp_path, lambda *a, **k: _law_document())
    monkeypatch.setattr(sys, "argv", ["articles.py", "129ac0000000089"])
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 5
    assert _written(tmp_path) == []


def test_a_full_run_with_no_shipped_diffs_at_all_refuses_rather_than_deleting(monkeypatch, tmp_path):
    # An empty FRONTEND_DIR (wrong path, empty checkout) used to build zero
    # laws and then "clean up" by deleting every existing articles/*.json.
    shipped = tmp_path / "frontend" / "public" / "data"
    shipped.mkdir(parents=True)
    stale = shipped / "articles" / "129AC0000000089.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}")
    monkeypatch.setattr(articles, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(articles, "FRONTEND_DIR", shipped)
    monkeypatch.setattr(articles, "fetch_law_data", lambda *a, **k: _law_document())
    monkeypatch.setattr(sys, "argv", ["articles.py", "--all"])
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 5
    assert stale.exists()


def test_main_does_not_save_when_the_day_changes_after_all_laws_are_built(monkeypatch, tmp_path):
    # A single-law run exits 3 at the per-law check, so the post-loop
    # sentinel -- the one that guards the moment right before anything is
    # written -- is never exercised without a second law that finishes
    # cleanly before the day rolls over.
    shipped = tmp_path / "frontend" / "public" / "data"
    _shipped_diff(shipped)
    (shipped / "140AC0000000045_2023-07-12_2023-07-13.json").write_text(
        json.dumps(
            _doc("2023-07-13", [_entry("183", paragraphs_after=[{"num": "1", "text": "本文"}])],
                 law_id="140AC0000000045", date_before="2023-07-12"),
            ensure_ascii=False,
        )
    )

    def fetch(law_id, asof):
        if law_id == "140AC0000000045":
            return _law_document(_tree(_article("183", "第百八十三条", "占有の性質の変更")))
        return _law_document()

    monkeypatch.setattr(articles, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(articles, "FRONTEND_DIR", shipped)
    monkeypatch.setattr(articles, "fetch_law_data", fetch)
    monkeypatch.setattr(sys, "argv", ["articles.py", "--all"])

    real_now = datetime.datetime.now
    calls = []

    class Clock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(1)
            base = real_now(tz)
            # Calls 1-3 are "today" plus each of the two laws' fetched_at --
            # all must land on the same day so both per-law checks pass.
            # Only the 4th call (the post-loop check) sees the day change.
            return base if len(calls) <= 3 else base + datetime.timedelta(days=1)

    monkeypatch.setattr(articles.datetime, "datetime", Clock)
    with pytest.raises(SystemExit) as exc:
        articles.main()
    assert exc.value.code == 3
    assert _written(tmp_path) == []


def test_resolve_current_calls_a_standalone_deleted_body_a_tombstone():
    # 民法733, 民法746 and 刑法178 were repealed by an amendment e-Gov records as
    # a modification: the body was replaced with the word 削除. The article is
    # still in today's index, so the status has to come from the body.
    index = articles.index_current_articles(
        _tree(_article("733", "第七百三十三条", text="削除"))
    )
    current = articles.resolve_current(index, "733", "modified")
    assert current["status"] == "deleted"
    assert current["source_article_num"] == "733"


def test_a_repeal_recorded_as_a_modification_loses_its_summary_and_links():
    # Both sides of the gate are the word 削除, so texts_match says True and
    # summary_is_safe finds nothing wrong. The status has to override them.
    refs = [{"ref": "第七百四十六条", "article_num": "746", "context": "c"}]
    entries = [
        _entry(
            "733",
            paragraphs_after=[{"num": "1", "text": "削除"}],
            paragraphs_before=[{"num": "1", "text": "女は、前婚の解消…"}],
            annotation={
                "plain_summary": "再婚禁止期間を定めたルール",
                "change_description": "d",
                "cross_references": refs,
            },
        )
    ]
    doc = _build(entries, _tree(_article("733", "第七百三十三条", text="削除")))
    page = doc["articles"][0]
    assert page["current"]["status"] == "deleted"
    assert page["current_summary"] is None
    assert page["related_articles"] == []
    # The note survives as a dated claim on its history card.
    assert page["changes"][0]["plain_summary"] == "再婚禁止期間を定めたルール"


def test_a_repeal_recorded_as_a_modification_still_shows_its_former_text():
    entries = [
        _entry(
            "733",
            paragraphs_after=[{"num": "1", "text": "削除"}],
            paragraphs_before=[{"num": "1", "text": "女は、前婚の解消…"}],
        )
    ]
    doc = _build(entries, _tree(_article("733", "第七百三十三条", text="削除")))
    page = doc["articles"][0]
    assert page["former"]["paragraphs"][0]["text"] == "女は、前婚の解消…"
    assert page["former"]["as_of"] == "2026-03-31"


def test_validate_rejects_a_deleted_page_with_empty_former_paragraphs():
    doc = {"source": SOURCE,
           "articles": [{"article_num": "733", "slug": "733", "label": "第七百三十三条",
                         "current": {"status": "deleted", "paragraphs": [{"num": "1", "text": "削除"}]},
                         "former": {"as_of": "2026-03-31", "label": "l", "paragraphs": []},
                         "current_summary": None,
                         "changes": [{"change_description": "d"}]}]}
    assert any("former text" in e for e in articles.validate_articles(doc))


def test_validate_rejects_a_tombstone_that_kept_a_current_summary():
    doc = {"source": SOURCE,
           "articles": [{"article_num": "733", "slug": "733", "label": "第七百三十三条",
                         "current": {"status": "deleted", "paragraphs": [{"num": "1", "text": "削除"}]},
                         "former": {"as_of": "2026-03-31", "label": "l",
                                    "paragraphs": [{"num": "1", "text": "旧"}]},
                         "current_summary": {"text": "s", "evidence_date": "2026-04-01"},
                         "changes": [{"change_description": "d"}]}]}
    assert any("current summary" in e for e in articles.validate_articles(doc))


def test_a_link_to_a_page_that_lost_its_summary_keeps_the_link_but_drops_the_context():
    # 著作権法121条 describes 122条の2 as 秘密保持命令違反; today's 122条の2 is
    # about 帳簿, which is why 122条の2's own page has no summary.
    refs = [{"ref": "第百二十二条の二", "article_num": "122_2", "context": "秘密保持命令違反の処罰"}]
    entries = [
        _entry(
            "121",
            paragraphs_after=[{"num": "1", "text": "本文"}],
            annotation={"plain_summary": "s", "change_description": "d", "cross_references": refs},
        ),
        _entry("122_2", paragraphs_after=[{"num": "1", "text": "昔の本文"}]),
    ]
    doc = _build(
        entries,
        _tree(
            _article("121", "第百二十一条"),
            _article("122_2", "第百二十二条の二", text="今日の本文"),
        ),
    )
    page = next(a for a in doc["articles"] if a["article_num"] == "121")
    target = next(a for a in doc["articles"] if a["article_num"] == "122_2")
    assert target["current_summary"] is None
    assert page["related_articles"][0]["slug"] == "122-2"
    assert page["related_articles"][0]["has_page"] is True
    assert page["related_articles"][0]["context"] == ""


def test_a_link_to_a_page_that_kept_its_summary_keeps_its_context():
    refs = [{"ref": "第三百八条", "article_num": "308", "context": "雇用関係の先取特権"}]
    entries = [
        _entry(
            "306",
            paragraphs_after=[{"num": "1", "text": "本文"}],
            annotation={"plain_summary": "s", "change_description": "d", "cross_references": refs},
        ),
        _entry("308", paragraphs_after=[{"num": "1", "text": "本文"}]),
    ]
    doc = _build(entries, _tree(_article("306", "第三百六条"), _article("308", "第三百八条")))
    page = next(a for a in doc["articles"] if a["article_num"] == "306")
    assert page["related_articles"][0]["context"] == "雇用関係の先取特権"


# --- the history card's time label is decided on the text, not on `type` ---


def test_summary_basis_of_a_normal_amendment_is_the_text_after_it():
    assert articles.summary_basis([{"num": "1", "text": "新しい本文"}]) == "after"


def test_summary_basis_of_a_deleted_entry_is_the_text_before_it():
    # A "deleted" entry carries paragraphs_after == [] (民法753/754, measured).
    assert articles.summary_basis([]) == "before"


def test_summary_basis_of_a_repeal_recorded_as_a_modification_is_before():
    # 民法733/746 and 刑法178 are typed "modified" and their new body is the
    # single word 削除. Keying the label on `type` labelled a description of the
    # repealed rule as a description of 削除.
    assert articles.summary_basis([{"num": "1", "text": "削除"}]) == "before"


def test_a_repeal_typed_as_a_modification_labels_its_card_改正直前():
    entries = [
        _entry(
            "733",
            "modified",
            paragraphs_after=[{"num": "1", "text": "削除"}],
            paragraphs_before=[{"num": "1", "text": "女性は…再婚することができない"}],
        )
    ]
    doc = _build(entries, _tree(_article("733", "第七百三十三条", text="削除")))
    change = doc["articles"][0]["changes"][0]
    assert change["type"] == "modified"
    assert change["summary_basis"] == "before"


def test_an_ordinary_amendment_labels_its_card_改正直後():
    entries = [_entry("306", paragraphs_after=[{"num": "1", "text": "本文"}])]
    doc = _build(entries, _tree(_article("306", "第三百六条", "一般の先取特権")))
    assert doc["articles"][0]["changes"][0]["summary_basis"] == "after"


def test_a_deleted_entry_still_labels_its_card_改正直前():
    entries = [
        _entry("753", "deleted", paragraphs_after=[]),
        _entry("754", "deleted", paragraphs_after=[]),
        _entry("753:754", "added"),
    ]
    doc = _build(entries, _tree(_article("753:754", "第七百五十三条及び第七百五十四条", text="削除")))
    page = next(a for a in doc["articles"] if a["article_num"] == "754")
    assert page["changes"][0]["summary_basis"] == "before"


# --- a history card's own note goes through the penalty check too ---


def test_a_card_summary_naming_a_penalty_absent_from_its_own_new_text_is_dropped():
    # 著作権法119: the amendment IS the 懲役 -> 拘禁刑 rename, so a note saying
    # the post-amendment article defines 懲役 contradicts the change_description
    # printed one line above it.
    entries = [
        _entry(
            "119",
            paragraphs_after=[{"num": "1", "text": "十年以下の拘禁刑"}],
            annotation={
                "plain_summary": "刑事罰(懲役・罰金)を定めるルール",
                "change_description": "「懲役」から「拘禁刑」に変更されました",
                "cross_references": [],
            },
        )
    ]
    doc = _build(entries, _tree(_article("119", "第百十九条", text="十年以下の拘禁刑")))
    change = doc["articles"][0]["changes"][0]
    assert change["plain_summary"] == ""
    # The diff's own prose about the rename is correct and stays.
    assert change["change_description"] == "「懲役」から「拘禁刑」に変更されました"


def test_a_card_summary_naming_a_penalty_its_own_new_text_still_carries_is_kept():
    # 道路交通法117条の2の2 / 118条, enforced 2024-11-01: 懲役 was law then, and
    # the card is dated. A blanket ban on the word would delete a true sentence.
    entries = [
        _entry(
            "118",
            paragraphs_after=[{"num": "1", "text": "三年以下の懲役又は五十万円以下の罰金"}],
            annotation={
                "plain_summary": "罰則(懲役や罰金)を定め…",
                "change_description": "d",
                "cross_references": [],
            },
        )
    ]
    doc = _build(entries, _tree(_article("118", "第百十八条", text="今日の本文")))
    assert doc["articles"][0]["changes"][0]["plain_summary"] == "罰則(懲役や罰金)を定め…"


def test_a_repealed_articles_card_summary_is_checked_against_its_former_text():
    # The card says 改正直前, so the text it describes is paragraphs_before.
    # Checking a repeal against its empty paragraphs_after would drop a note
    # that is true of the version the card is dated to.
    entries = [
        _entry(
            "178",
            "modified",
            paragraphs_after=[{"num": "1", "text": "削除"}],
            paragraphs_before=[{"num": "1", "text": "三年以上の懲役に処する"}],
            annotation={
                "plain_summary": "3年以上の懲役にあたる準強制わいせつの規定",
                "change_description": "d",
                "cross_references": [],
            },
        )
    ]
    doc = _build(entries, _tree(_article("178", "第百七十八条", text="削除")))
    change = doc["articles"][0]["changes"][0]
    assert change["summary_basis"] == "before"
    assert change["plain_summary"] == "3年以上の懲役にあたる準強制わいせつの規定"


# --- the lossy [表] marker must not be read as agreement ---


def test_texts_do_not_match_when_a_table_placeholder_is_on_either_side():
    # diff.py renders every TableStruct as "[表]", so an article whose only
    # change was inside a table produces the identical string on both sides.
    after = [{"num": "1", "text": "次の表のとおりとする。\n[表]"}]
    current = [{"num": "1", "text": "次の表のとおりとする。\n[表]"}]
    assert articles.texts_match(after, current) is False


def test_an_article_containing_a_table_ships_without_a_current_summary():
    entries = [_entry("306", paragraphs_after=[{"num": "1", "text": "[表]"}])]
    doc = _build(entries, _tree(_article("306", "第三百六条", text="[表]")))
    page = doc["articles"][0]
    assert page["current_summary"] is None
    assert page["related_articles"] == []


# --- a reference naming a range of articles never becomes a link ---


# One case per entry of MULTI_ARTICLE_CONNECTIVES, so dropping any single
# connective goes red on its own case and names itself in the failure.
MULTI_ARTICLE_REFS = [
    "第七百七十八条から第七百七十八条の四まで",
    "第三百六条乃至第七百六十六条",
    "第三百六条及び第七百六十六条",
    "第三百六条並びに第七百六十六条",
    "第三百六条又は第七百六十六条",
    "第三百六条若しくは第七百六十六条",
    "第三百六条、第七百六十六条",
    "第三百六条・第七百六十六条",
]


@pytest.mark.parametrize("ref", MULTI_ARTICLE_REFS)
def test_a_reference_naming_more_than_one_article_is_not_linked(ref):
    # startswith against the alias table would make the whole phrase a link to
    # the first article it names. 及び/又は are the inner level of statutory
    # drafting and 並びに/若しくは the outer one, so guarding only one of each
    # pair guards only half the shapes.
    resolved, unresolved = articles.resolve_cross_references(
        [{"ref": ref, "article_num": "", "context": "c"}], ALIASES, "2"
    )
    assert resolved[0]["has_page"] is False
    assert resolved[0]["slug"] is None
    assert unresolved == 1


def test_every_multi_article_connective_has_a_case_of_its_own():
    # MULTI_ARTICLE_REFS is the guard; this is the guard on the guard. A
    # connective added to the constant without a case would otherwise ship
    # untested, and its mutation proof would pass vacuously.
    for connective in articles.MULTI_ARTICLE_CONNECTIVES:
        assert any(connective in ref for ref in MULTI_ARTICLE_REFS), connective


def test_a_reference_naming_one_article_still_links():
    resolved, unresolved = articles.resolve_cross_references(
        [{"ref": "第七百六十六条の規定により", "article_num": "766", "context": "c"}],
        ALIASES,
        "306",
    )
    assert resolved[0]["slug"] == "766"
    assert unresolved == 0


# --- a link's description needs positive evidence, not merely no evidence ---


def test_a_link_to_a_pageless_target_keeps_the_link_and_loses_the_description():
    # 民法740's link to 第七百三十一条: 731 has no page here, so nothing ever
    # compared its text against today's. An unchecked claim gets the same
    # answer as a claim checked and found stale.
    refs = [
        {"ref": "第七百六十六条", "article_num": "766", "context": "離婚後の子の監護について"},
    ]
    entries = [
        _entry(
            "306",
            paragraphs_after=[{"num": "1", "text": "本文"}],
            annotation={"plain_summary": "s", "change_description": "d", "cross_references": refs},
        )
    ]
    doc = _build(entries, _tree(_article("306", "第三百六条", text="本文")))
    related = doc["articles"][0]["related_articles"]
    assert len(related) == 1
    # 766 has no page in this build, so the alias table has no entry for it.
    assert related[0]["has_page"] is False
    assert related[0]["context"] == ""


def test_a_link_to_a_target_that_kept_its_summary_keeps_its_description():
    refs = [{"ref": "第七百六十六条", "article_num": "766", "context": "離婚後の子の監護について"}]
    entries = [
        _entry(
            "306",
            paragraphs_after=[{"num": "1", "text": "本文"}],
            annotation={"plain_summary": "s", "change_description": "d", "cross_references": refs},
        ),
        _entry("766", paragraphs_after=[{"num": "1", "text": "本文"}]),
    ]
    doc = _build(
        entries,
        _tree(_article("306", "第三百六条", text="本文"), _article("766", "第七百六十六条", text="本文")),
    )
    page = next(a for a in doc["articles"] if a["article_num"] == "306")
    assert page["related_articles"][0]["slug"] == "766"
    assert page["related_articles"][0]["context"] == "離婚後の子の監護について"
