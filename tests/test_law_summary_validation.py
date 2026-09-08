import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import law_summary
from law_summary import validate_summary


# Stands in for what build_evidence() returns: the law's own words. Every
# keyword in valid_summary() appears here, because that is now the rule.
EVIDENCE = """## 目次
第一章　総則
第二章　殺人の罪
第三章　窃盗及び強盗の罪

## 各条の見出し
（国内犯）
（殺人）
（窃盗）
（罰金）
（刑罰の種類）
（犯罪の成立）
（拘禁刑）

## 第一条（全文）
（国内犯）第一条この法律は、日本国内において罪を犯したすべての者に適用する。"""


def valid_summary(**overrides):
    summary = {
        "description": (
            "刑法は、殺人や窃盗、詐欺など犯罪として処罰される行為と、その刑罰の内容を定めた"
            "法律です。どのような行為が犯罪にあたるのかを明確に規定しています。"
        ),
        "scope": "日本国内で犯罪行為を行ったすべての人に適用されます。",
        "keywords": ["犯罪", "刑罰", "拘禁刑", "罰金", "殺人"],
    }
    summary.update(overrides)
    return summary


def test_valid_summary_passes():
    assert validate_summary(valid_summary(), EVIDENCE) == []


def test_abolished_penalty_name_in_description_is_rejected():
    summary = valid_summary(
        description=(
            "刑法は、犯罪を犯した場合にどのような刑罰（懲役、罰金など）が科せられるのかを"
            "明確に規定した法律です。社会の秩序を守るために定められています。"
        )
    )
    errors = validate_summary(summary, EVIDENCE)
    assert any("懲役" in e for e in errors)


def test_abolished_penalty_name_in_keywords_is_rejected():
    # The 刑法 summary that shipped had 懲役 in keywords as well as in prose.
    errors = validate_summary(valid_summary(keywords=["犯罪", "刑罰", "懲役"]), EVIDENCE)
    assert any("懲役" in e for e in errors)


@pytest.mark.parametrize("term", ["禁錮", "禁固", "禁こ"])
def test_every_spelling_of_the_abolished_kinko_is_rejected(term):
    # 禁固 is the newspaper spelling; a ban listing only 禁錮 lets the same
    # mistake through one character later.
    errors = validate_summary(valid_summary(keywords=["犯罪", term]), EVIDENCE)
    assert any(term in e for e in errors)


def test_missing_key_is_reported_alone():
    summary = valid_summary()
    del summary["scope"]
    assert validate_summary(summary, EVIDENCE) == ["missing key: scope"]


def test_too_many_keywords_is_rejected():
    errors = validate_summary(valid_summary(keywords=["a", "b", "c", "d", "e", "f"]), EVIDENCE)
    assert any("keywords count" in e for e in errors)


def test_empty_keyword_is_rejected():
    errors = validate_summary(valid_summary(keywords=["犯罪", "  "]), EVIDENCE)
    assert any("non-empty" in e for e in errors)


def test_short_description_is_rejected():
    errors = validate_summary(valid_summary(description="短い説明"), EVIDENCE)
    assert any("description length" in e for e in errors)


# --- the save-path contract, not just the validator ---------------------------
#
# validate_summary being correct does not mean main() calls it. These pin the
# behaviour an external reviewer pointed at: a rejected summary must exit 2 and
# leave the timeline file byte-identical.

def _timeline_fixture(tmp_path):
    timeline_dir = tmp_path / "timelines"
    timeline_dir.mkdir()
    path = timeline_dir / "140AC0000000045.json"
    path.write_text(
        json.dumps(
            {
                "law_title": "刑法",
                "law_num": "明治四十年法律第四十五号",
                "revision_count": 16,
                "timeline": [],
                "summary": {"description": "既存の説明", "scope": "既存", "keywords": ["既存"]},
            },
            ensure_ascii=False,
        )
    )
    return path


def _raw_fixture(tmp_path):
    """main() refuses to run without today's law text, so give it today's.

    The date is computed rather than hardcoded because the guard compares
    against today in Asia/Tokyo: a fixed filename would pass on the day it was
    written and fail every day after.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    today = datetime.datetime.now(law_summary.JST).date().isoformat()
    (raw_dir / f"140AC0000000045_{today}.json").write_text(
        json.dumps(
            {
                "law_full_text": {
                    "tag": "Law",
                    "attr": {},
                    "children": [
                        {
                            "tag": "Chapter",
                            "attr": {},
                            "children": [
                                {"tag": "ChapterTitle", "attr": {}, "children": ["第一章　総則"]},
                                {
                                    "tag": "Article",
                                    "attr": {"Num": "1"},
                                    "children": [
                                        {"tag": "ArticleCaption", "attr": {}, "children": ["（国内犯）"]},
                                        {
                                            "tag": "Paragraph",
                                            "attr": {},
                                            "children": [{
                                                "tag": "ParagraphSentence",
                                                "attr": {},
                                                "children": [{
                                                    "tag": "Sentence",
                                                    "attr": {},
                                                    "children": ["犯罪 刑罰 拘禁刑 罰金 殺人"],
                                                }],
                                            }],
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                }
            },
            ensure_ascii=False,
        )
    )
    return raw_dir


def _run_main(monkeypatch, tmp_path, generated):
    _raw_fixture(tmp_path)
    monkeypatch.setattr(law_summary, "DATA_DIR", tmp_path)
    monkeypatch.setattr(law_summary, "FRONTEND_DIR", tmp_path / "frontend")
    monkeypatch.setattr(law_summary, "load_env", lambda: None)
    monkeypatch.setattr(law_summary, "generate_summary", lambda *a, **k: generated)
    monkeypatch.setattr(sys, "argv", ["law_summary.py", "140AC0000000045"])
    law_summary.main()


def test_main_exits_2_and_saves_nothing_when_validation_fails(monkeypatch, tmp_path):
    path = _timeline_fixture(tmp_path)
    before = path.read_bytes()

    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, tmp_path, valid_summary(keywords=["犯罪", "懲役"]))

    assert exc.value.code == 2
    assert path.read_bytes() == before


def test_main_saves_a_valid_summary(monkeypatch, tmp_path):
    path = _timeline_fixture(tmp_path)
    generated = valid_summary()

    _run_main(monkeypatch, tmp_path, generated)

    assert json.loads(path.read_text())["summary"] == generated


# --- keywords must have a basis in the law text -------------------------------
#
# The validator cannot judge prose, but a keyword is a noun: either the word is
# in the law or it is not. This is the cheapest possible check on the failure
# the script exists to prevent — a plausible-sounding institution the law does
# not contain.

def test_keyword_absent_from_the_law_text_is_rejected():
    errors = validate_summary(valid_summary(keywords=["犯罪", "行政指導"]), EVIDENCE)
    assert any("行政指導" in e for e in errors)


def test_keywords_present_in_the_law_text_pass():
    assert validate_summary(valid_summary(keywords=["殺人", "窃盗"]), EVIDENCE) == []


def test_empty_evidence_is_refused_outright():
    # A caller that lost its evidence must not get a pass by default.
    errors = validate_summary(valid_summary(), "")
    assert any("evidence" in e for e in errors)


# --- the evidence must actually reach the model -------------------------------
#
# Gate3 finding: nothing pinned the hand-off. generate_summary could be called
# with the wrong string — or the evidence dropped from the prompt entirely —
# and every test above would stay green, because they all mock it away.

def test_the_prompt_contains_the_evidence(monkeypatch):
    seen = {}

    def fake_complete_json(client, model, prompt, max_tokens):
        seen["prompt"] = prompt
        return valid_summary()

    monkeypatch.setattr(law_summary, "complete_json", fake_complete_json)
    monkeypatch.setattr(law_summary.anthropic, "Anthropic", lambda *a, **k: object())

    law_summary.generate_summary("刑法", "明治四十年法律第四十五号", "刑事", 16, EVIDENCE)

    assert EVIDENCE in seen["prompt"], "the law text never reached the model"
    assert "刑法" in seen["prompt"]


def test_single_character_keyword_is_rejected():
    # 「刑」 passes the grounding check because it occurs inside 「刑罰」, so the
    # evidence rule cannot catch it. 刑法 shipped it as a keyword.
    errors = validate_summary(valid_summary(keywords=["刑", "殺人"]), EVIDENCE)
    assert any("too short" in e for e in errors)
