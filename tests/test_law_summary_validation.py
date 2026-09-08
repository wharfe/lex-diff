import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import law_summary
from law_summary import validate_summary


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
    assert validate_summary(valid_summary()) == []


def test_abolished_penalty_name_in_description_is_rejected():
    summary = valid_summary(
        description=(
            "刑法は、犯罪を犯した場合にどのような刑罰（懲役、罰金など）が科せられるのかを"
            "明確に規定した法律です。社会の秩序を守るために定められています。"
        )
    )
    errors = validate_summary(summary)
    assert any("懲役" in e for e in errors)


def test_abolished_penalty_name_in_keywords_is_rejected():
    # The 刑法 summary that shipped had 懲役 in keywords as well as in prose.
    errors = validate_summary(valid_summary(keywords=["犯罪", "刑罰", "懲役"]))
    assert any("懲役" in e for e in errors)


@pytest.mark.parametrize("term", ["禁錮", "禁固", "禁こ"])
def test_every_spelling_of_the_abolished_kinko_is_rejected(term):
    # 禁固 is the newspaper spelling; a ban listing only 禁錮 lets the same
    # mistake through one character later.
    errors = validate_summary(valid_summary(keywords=["犯罪", term]))
    assert any(term in e for e in errors)


def test_missing_key_is_reported_alone():
    summary = valid_summary()
    del summary["scope"]
    assert validate_summary(summary) == ["missing key: scope"]


def test_too_many_keywords_is_rejected():
    errors = validate_summary(valid_summary(keywords=["a", "b", "c", "d", "e", "f"]))
    assert any("keywords count" in e for e in errors)


def test_empty_keyword_is_rejected():
    errors = validate_summary(valid_summary(keywords=["犯罪", "  "]))
    assert any("non-empty" in e for e in errors)


def test_short_description_is_rejected():
    errors = validate_summary(valid_summary(description="短い説明"))
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


def _run_main(monkeypatch, tmp_path, generated):
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
