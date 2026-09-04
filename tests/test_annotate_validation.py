"""Guards that keep a malformed model answer out of the shipped data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from annotate import validate_annotation, validate_pr_summary
from llm import strip_code_fence


def good_summary():
    return {
        "title": "t", "summary": "s", "impact": "i", "background": "b",
        "key_changes": [{"theme": "th", "description": "d"}],
    }


def test_valid_summary_passes():
    assert validate_pr_summary(good_summary()) == []


def test_missing_key_changes_is_rejected():
    """pr-summary.tsx maps over key_changes: absent reaches the build as
    undefined.map and fails it, so absent must not validate as empty."""
    s = good_summary()
    del s["key_changes"]
    assert any("key_changes is missing" in e for e in validate_pr_summary(s))


def test_key_changes_as_a_string_is_rejected():
    s = good_summary()
    s["key_changes"] = "まとめ"
    assert any("not a list" in e for e in validate_pr_summary(s))


def test_blank_change_fields_are_rejected():
    s = good_summary()
    s["key_changes"] = [{"theme": "  ", "description": "d"}]
    assert any("theme" in e for e in validate_pr_summary(s))


def test_non_object_summary_is_rejected():
    assert validate_pr_summary(["a"]) 
    assert validate_pr_summary(None)


def test_annotation_guards():
    ok = {"plain_summary": "p", "change_description": "c", "cross_references": []}
    assert validate_annotation(ok) == []
    assert validate_annotation("文字列")  # non-dict must not raise
    bad = dict(ok, cross_references=["第一条"])
    assert any("cross_references[0]" in e for e in validate_annotation(bad))


def test_strip_code_fence_handles_a_fence_without_a_newline():
    assert strip_code_fence('```json{"a": 1}```') == '{"a": 1}'
    assert strip_code_fence('```\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'
