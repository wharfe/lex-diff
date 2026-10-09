import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import annotate
from diff import amendment_titles_on
from enrich import proposer_from_timeline


def _rev(date, title, rid="r"):
    return {"amendment_enforcement_date": date, "amendment_law_title": title,
            "law_revision_id": rid}


# --- several amending laws can take effect on the same day (#23) ---


def test_every_law_taking_effect_that_day_is_named():
    # 刑法 2025-06-01: the 拘禁刑 merger and a 刑事訴訟法 amendment land at
    # once, and one diff cannot tell their changes apart.
    revisions = [
        _rev("2025-06-01", "刑事訴訟法等の一部を改正する法律"),
        _rev("2025-06-01", "刑法等の一部を改正する法律"),
        _rev("2023-07-13", "刑法及び刑事訴訟法の一部を改正する法律"),
    ]
    titles = amendment_titles_on(revisions, "2025-06-01", "刑法等の一部を改正する法律")
    assert titles == ["刑法等の一部を改正する法律", "刑事訴訟法等の一部を改正する法律"]


def test_a_single_law_that_day_is_just_its_own_title():
    revisions = [_rev("2026-06-24", "民法の一部を改正する法律")]
    assert amendment_titles_on(revisions, "2026-06-24", "民法の一部を改正する法律") == [
        "民法の一部を改正する法律"
    ]


def test_the_snapshots_own_title_is_kept_even_if_revisions_lack_it():
    assert amendment_titles_on([], "2026-06-24", "A法") == ["A法"]


def _diff_doc(titles):
    return {
        "law_title": "刑法",
        "date_before": "2025-05-31",
        "date_after": "2025-06-01",
        "revision_after": {
            "amendment_law_title": "／".join(titles),
            "amendment_law_titles": titles,
        },
        "diffs": [{
            "type": "modified", "article_num": "1", "title_after": "第一条",
            "is_suppl": False, "section_path": [],
            "lines_before": ["旧"], "lines_after": ["新"],
            "paragraphs_before": [], "paragraphs_after": [],
        }],
    }


def test_the_summary_prompt_refuses_to_attribute_a_same_day_diff_to_one_law():
    prompt = annotate.build_pr_summary_prompt(_diff_doc(["A法", "B法"]))
    assert "A法" in prompt and "B法" in prompt
    assert "どの変更がどの法令によるものか" in prompt


def test_a_single_law_prompt_is_unchanged():
    # The article-annotation cache is keyed on prompt text; the summary prompt
    # for an ordinary diff must stay byte-identical to what it was.
    prompt = annotate.build_pr_summary_prompt(_diff_doc(["A法"]))
    assert "改正法令: A法\n" in prompt
    assert "どの変更がどの法令によるものか" not in prompt


# --- a diff's proposer comes from its timeline entry, not a fresh search ---


def test_a_diffs_proposer_is_copied_by_revision_id():
    timeline = {"timeline": [
        {"law_revision_id": "a", "proposer": {"submission_type": "閣法"}},
        {"law_revision_id": "b"},
    ]}
    assert proposer_from_timeline({"revision_after": {"law_revision_id": "a"}},
                                  timeline) == {"submission_type": "閣法"}
    assert proposer_from_timeline({"revision_after": {"law_revision_id": "b"}},
                                  timeline) is None
    assert proposer_from_timeline({"revision_after": {"law_revision_id": "z"}},
                                  timeline) is None


# --- the diff is the one place that names its amendment (#23, Gate 2 r2) ---

from diff import tables_changed
from explainer import apply_diff, build_prompt
from enrich import diff_proposer


def _change(diff_id="d"):
    return {"year": "2025", "source_title": "刑事訴訟法等の一部を改正する法律",
            "enforcement_date": "2025-06-01", "diff_id": diff_id, "grounded": True}


def _same_day_diff():
    return {"pr_summary": {"title": "t"},
            "revision_after": {"amendment_law_title": "A法／B法",
                               "amendment_law_titles": ["A法", "B法"]}}


def test_the_explainer_names_a_grounded_change_by_its_diff():
    # The timeline entry that survived dedupe names one of the two laws; the
    # 174 拘禁刑 changes would otherwise be explained as 刑事訴訟法's.
    c = apply_diff(_change(), _same_day_diff())
    assert c["source_title"] == "A法／B法"
    prompt = build_prompt("刑法", "n", "c", "s", [c])
    assert "どの変更がどの法令によるものか" in prompt


def test_the_explainer_prompt_for_a_single_law_diff_says_nothing_extra():
    single = {"pr_summary": {"title": "t"},
              "revision_after": {"amendment_law_title": "A法"}}
    c = apply_diff(_change(), single)
    assert c["source_title"] == "A法"
    assert "どの変更がどの法令によるものか" not in build_prompt("刑法", "n", "c", "s", [c])


def test_a_missing_diff_downgrades_to_ungrounded():
    c = apply_diff(_change(), None)
    assert c["grounded"] is False


def test_a_same_day_diff_has_no_single_proposer():
    # Even when the diff itself names only one law (published before titles
    # were collected), the timeline says how many took effect that day.
    timeline = {"timeline": [
        {"law_revision_id": "a", "enforcement_date": "2025-04-01", "proposer": {"x": 1}},
        {"law_revision_id": "b", "enforcement_date": "2025-04-01", "proposer": {"y": 2}},
        {"law_revision_id": "c", "enforcement_date": "2026-06-24", "proposer": {"z": 3}},
    ]}
    old_single_title = {"date_after": "2025-04-01", "revision_after": {"law_revision_id": "a"}}
    assert diff_proposer(old_single_title, timeline) is None
    single = {"date_after": "2026-06-24", "revision_after": {"law_revision_id": "c"}}
    assert diff_proposer(single, timeline) == {"z": 3}


# --- a table change is invisible to compute_diff, so it withholds the diff ---


def _law(table_text, num="1"):
    return {"tag": "Law", "children": [
        {"tag": "LawBody", "children": [
            {"tag": "MainProvision", "children": [
                {"tag": "Article", "children": [
                    {"tag": "TableStruct", "children": [table_text]}]}]},
            {"tag": "AppdxTable", "attr": {"Num": num}, "children": ["別表"]},
        ]},
    ]}


def test_a_changed_table_inside_an_article_is_detected():
    assert tables_changed(_law("旧"), _law("新")) is True


def test_a_changed_appendix_table_is_detected():
    before = _law("同")
    after = _law("同")
    after["children"][0]["children"][1]["children"] = ["別表（改）"]
    assert tables_changed(before, after) is True


def test_an_attribute_only_difference_is_not_a_change():
    # 労働基準法 2024-05-31: AppdxTable Num="1" vanished, content identical.
    assert tables_changed(_law("同", num="1"), _law("同", num=None)) is False
