# 条文ページ（issue #4）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 出荷済み diff と今日の e-Gov 本文から、条文1本=1ページの静的ページ（現在163枚）を生成し、本文と解説の版がズレているページでは解説を出さない。

**Architecture:** 新規 Python スクリプト `scripts/articles.py` が、出荷済み diff JSON（改正履歴・解説）と、生成と同じ実行で取得した e-Gov 法令全文（現在の条文）を突き合わせ、法令ごとに `frontend/public/data/articles/<lawId>.json` を書く。Next.js 側は新しい動的ルート `/law/[lawId]/article/[articleSlug]` がその JSON を読んで静的生成する。**条番号の解釈はすべて Python 側で完結させ、TypeScript 側には slug 変換関数を置かない。**

**Tech Stack:** Python 3.13（uv / pytest / httpx）、Next.js App Router（TypeScript strict / SSG）

**Spec:** `docs/design-debate/article-pages/spec.md`

## Global Constraints

spec から逐語で持ってくる、全タスクに効く制約:

- **コード内コメントは英語。利用者向けテキストは日本語。**
- **「現在の条文」と断定しない。** ページの見出しは必ず「現在の条文（YYYY年M月D日時点）」。
- **ページ数をテストに焼かない。** 検査は「生成 JSON の slug 総数 == 静的生成された HTML 数」。現在の出荷データでは 163 だが、この値は定数として書かない。
- **`:` を含む `article_num` は slug 化しない**（`ValueError`）。範囲エントリはページを持たない。
- **附則（`is_suppl` が真）は一切扱わない。**
- **未施行（`date_after > 生成時の JST 日付`）の diff は対象外。**
- **新しい LLM 生成を足さない。** 既存 `annotation` を組み替えるだけ。
- **取得失敗時のフォールバックを書かない。** 古いファイルへ落ちる経路を作らない。
- **JST は `ZoneInfo("Asia/Tokyo")`。**
- 終了コード: `2` = 検証失敗、`3` = 生成中に JST 日付が変わった。
- 既存の `scripts/` からの再利用（再実装しない）: `fetch.fetch_law_data(law_id, asof) -> dict`、`lawtext.walk_tags(node, tags, stop_at) -> list[dict]`、`lawtext.extract_text(node) -> str`、`diff.format_paragraph(node) -> str`、`diff.format_item(node, indent) -> str`、
`diff.find_section_path(node, article_num) -> list[str] | None`。
- **`diff.py` を変更しない。** `find_articles` の caption 取りこぼしは既知バグだが本計画の対象外（別 issue）。
- テストは既存の書き方に合わせる: 先頭で `sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))`、合成フィクスチャ、`monkeypatch` で外部 IO を差し替える。

---

## File Structure

| ファイル | 責務 |
|---|---|
| `scripts/articles.py`（新規） | 条文ページ用データの生成。全ロジックをピュア関数に分け、`main()` だけが IO を持つ |
| `tests/test_articles.py`（新規） | `articles.py` のピュア関数と `main()` 経路 |
| `tests/test_shipped_data.py`（変更） | 出荷済み `articles/*.json` に対する検査 |
| `.gitignore`（変更） | `data/articles/` を追加 |
| `CLAUDE.md`（変更） | `data/` の説明と scripts 一覧を更新 |
| `frontend/lib/types.ts`（変更） | 条文ページの型 |
| `frontend/lib/data.ts`（変更） | `articles/` の読み出し |
| `frontend/lib/format.ts`（新規） | 日付の和文表記。`new Date()` を使わない理由をここに持つ |
| `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx`（新規） | ページ本体・`generateStaticParams`・`generateMetadata` |
| `frontend/components/article-text.tsx`（新規） | 現在の条文と、削除条文の「改正直前の条文」 |
| `frontend/components/article-history.tsx`（新規） | 改正履歴カード |
| `frontend/components/article-links.tsx`（新規） | 関連する条文 |
| `frontend/app/law/[lawId]/page.tsx`（変更） | 「改正された条文」一覧＝条文ページへの唯一のクロール経路 |
| `frontend/components/diff-viewer.tsx`（変更） | 各本則カードに anchor と条文ページへのリンク |
| `frontend/app/sitemap.ts`（変更） | 条文ページを追加 |

---

## Task 1: 条番号の変換（ピュア関数）

**Files:**
- Create: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: なし
- Produces: `article_slug(article_num: str) -> str`、`display_num(article_num: str) -> str`、`is_range_num(article_num: str) -> bool`、`range_members(article_num: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'articles'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（9 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): 条番号の slug と日本語表記の変換を足す"
```

---

## Task 2: 出荷済み diff から対象条文と改正履歴を集める

**Files:**
- Modify: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: Task 1 の `is_range_num` / `range_members` / `article_slug`
- Produces: `collect_changes(diff_docs: list[dict], today: str) -> dict[str, list[dict]]` — 条番号 → 改正エントリのリスト（施行日降順）。各エントリは `{"diff_id", "enforcement_date", "year", "type", "amendment_law_title", "change_description", "plain_summary", "cross_references", "section_path", "paragraphs_before", "paragraphs_after", "date_before"}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles.py に追記

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v -k 'collect or range or suppl or unenforced or newest'`
Expected: FAIL — `AttributeError: module 'articles' has no attribute 'collect_changes'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py に追記


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（14 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): 出荷済み diff から対象条文と改正履歴を集める"
```

---

## Task 3: 今日の本文を索引し、条文を解決する

**Files:**
- Modify: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: Task 1・2、および `lawtext.walk_tags` / `lawtext.extract_text` / `diff.format_paragraph`
- Produces: `index_current_articles(law_full_text: dict) -> dict[str, dict]`、`extract_article_body(node: dict) -> dict`（`{"label", "caption", "paragraphs"}`）、`resolve_current(index: dict, article_num: str, latest_type: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles.py に追記


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


def test_texts_do_not_match_when_only_the_paragraph_numbers_differ():
    after = [{"num": "1", "text": "あ"}, {"num": "2", "text": "い"}]
    current = [{"num": "1", "text": "あ"}, {"num": "3", "text": "い"}]
    assert articles.texts_match(after, current) is False


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v -k 'resolve or extract or index'`
Expected: FAIL — `AttributeError: module 'articles' has no attribute 'extract_article_body'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py の import に追記
from lawtext import extract_text, walk_tags
from diff import format_paragraph, find_section_path

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（20 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): 今日の本文を索引し、削除条文の欠番まで解決する"
```

---

## Task 4: 本文と解説の版整合ゲート

**Files:**
- Modify: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: Task 3 の `resolve_current` の戻り
- Produces: `texts_match(paragraphs_after: list[dict], current_paragraphs: list[dict]) -> bool`、`ABOLISHED_PENALTIES: set[str]`、`summary_is_safe(summary: str, current_text: str) -> bool`

**なぜこのタスクがあるか**: 出荷済み diff は実際の法令から5〜24か月遅れており、162条文中30条文で本文が変わっている。刑法183条は本文「三年以下の拘禁刑」／解説「3年以下の懲役」、著作権法122条の2は本文が帳簿義務違反の罰則／解説が秘密保持命令違反の刑罰。後者は古いのではなく別の条文の説明。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles.py に追記


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v -k 'texts_match or summary_is_safe or abolished'`
Expected: FAIL — `AttributeError: module 'articles' has no attribute 'texts_match'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py に追記

# 禁固 is the newspaper spelling and 禁こ the kana one; a list holding only 禁錮
# lets the same claim through in a different dress.
ABOLISHED_PENALTIES = {"懲役", "禁錮", "禁固", "禁こ"}


def _normalise(text: str) -> str:
    # Line endings and trailing spaces are formatting. Everything else is the
    # provision, and a difference there means the note describes another text.
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def texts_match(paragraphs_after: list[dict], current_paragraphs: list[dict]) -> bool:
    """Whether the note's article and today's article are the same text."""
    if len(paragraphs_after) != len(current_paragraphs):
        return False
    # spec §4 says "段落番号と本文". Both sides take num from Paragraph@Num
    # (measured: shipped 民法772条 carries "1".."4"), so it is comparable.
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（29 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): 本文と解説の版整合ゲートを足す"
```

---

## Task 5: 関連条文の解決

**Files:**
- Modify: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: Task 1 の `article_slug`
- Produces: `resolve_cross_references(refs: list[dict], alias_to_num: dict[str, str], self_num: str) -> tuple[list[dict], int]`（解決済みリストと未解決件数）、`build_alias_table(pages: dict[str, dict]) -> dict[str, str]`

**なぜこのタスクがあるか**: 出荷データの `cross_references` 665件は LLM の自由記述で、他法令を指すものが34件、`article_num` が空のものが10件、表記ゆれ（`_` / `-` / `の`）が混在する。`article_num` を素直に信じると「民法第八百十七条の二」が育児介護休業法の条文を指す。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles.py に追記


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v -k 'cross_reference or alias'`
Expected: FAIL — `AttributeError: module 'articles' has no attribute 'resolve_cross_references'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py に追記


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（36 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): 関連条文を条名で解決し、他法令・附則・自己参照を弾く"
```

---

## Task 6: 法令単位 JSON の構築と保存前検証

**Files:**
- Modify: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: Task 1〜5 すべて
- Produces: `build_law_articles(law_id, law_title, changes, index, source) -> dict`、`validate_articles(doc: dict) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles.py に追記


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v -k 'build or validate or summary_is'`
Expected: FAIL — `AttributeError: module 'articles' has no attribute 'build_law_articles'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py に追記

_SLUG_RE = re.compile(r"^[0-9]+(-[0-9]+)*$")


def _num_sort_key(article_num: str) -> tuple[int, ...]:
    """第3条 before 第241条, 第117条の2の2 between 第117条 and 第118条."""
    return tuple(int(part) for part in article_num.split("_"))


def build_law_articles(
    law_id: str, law_title: str, changes: dict[str, list[dict]], law_full_text: dict, source: dict
) -> dict:
    """The shipped shape for one law.

    Takes the whole tree, not just the article index: the section path is read
    from today's text too. See the provenance table in spec §5 -- everything a
    "current" block shows comes from today's fetch or from a gated field, and
    the section path was the last one still coming from the shipped diff.
    """
    index = index_current_articles(law_full_text)
    pages: dict[str, dict] = {}
    for num, history in changes.items():
        latest = history[0]
        current = resolve_current(index, num, latest["type"])
        current_text = "".join(p["text"] for p in current["paragraphs"])

        # The gate. The note and the body must be the same version, and the note
        # must not name a penalty the body no longer carries.
        matched = texts_match(latest["paragraphs_after"], current["paragraphs"])
        safe = summary_is_safe(latest["plain_summary"], current_text)
        current_summary = (
            {"text": latest["plain_summary"], "evidence_date": latest["enforcement_date"]}
            if matched and safe and latest["plain_summary"]
            else None
        )

        former = None
        if latest["type"] == "deleted":
            former = {
                "as_of": latest["date_before"],
                "label": latest.get("title_before") or "",
                "paragraphs": latest["paragraphs_before"],
            }

        pages[num] = {
            "article_num": num,
            "slug": article_slug(num),
            "display_num": display_num(num),
            # Today's ArticleTitle only. Falling back to the diff's
            # title_before would put a past heading into the alias table and
            # reopen the hole spec §5's provenance table closed; an empty label
            # is caught by validate_articles instead.
            "label": current["source_label"],
            "caption": current["caption"],
            # Today's tree, not the diff's: 編章の移動 would otherwise leave the
            # breadcrumb describing a structure the law no longer has.
            #
            # Looked up by the number that resolved, not by `num`: a deleted
            # article is not an Article node today, so find_section_path(tree,
            # "753") returns None while the range it folded into, "753:754",
            # returns 第四編 親族 › 第二章 婚姻 › 第二節 婚姻の効力 (measured
            # 2026-09-22). Using `num` would blank the breadcrumb on exactly the
            # two pages whose breadcrumb matters most.
            "section_path": find_section_path(law_full_text, current["source_article_num"]) or [],
            "current": {
                "status": current["status"],
                "source_article_num": current["source_article_num"],
                "source_label": current["source_label"],
                "paragraphs": current["paragraphs"],
            },
            "current_summary": current_summary,
            "former": former,
            "changes": [
                {
                    "diff_id": c["diff_id"],
                    "enforcement_date": c["enforcement_date"],
                    "year": c["year"],
                    "type": c["type"],
                    "amendment_law_title": c["amendment_law_title"],
                    "change_description": c["change_description"],
                    # Kept even when it cannot be the current description: on a
                    # history card it is a dated claim, which is true.
                    "plain_summary": c["plain_summary"],
                    # Plain text on the card, never links. A reference written
                    # about an older version of this article may point at an
                    # article that has since moved.
                    "cross_references": [
                        {"ref": r.get("ref", ""), "context": r.get("context", "")}
                        for r in c["cross_references"]
                    ],
                }
                for c in history
            ],
            "related_articles": [],
            # Only a page whose text still matches may show current links. The
            # gate governs the whole "what this article is about" block, not
            # just its prose -- spec §4.
            "_refs": latest["cross_references"] if current_summary else [],
        }

    aliases = build_alias_table(pages)
    unresolved_total = 0
    for num, page in pages.items():
        page["related_articles"], unresolved = resolve_cross_references(
            page.pop("_refs"), aliases, num
        )
        unresolved_total += unresolved
    print(f"  cross references: {unresolved_total} unresolved")

    return {
        "law_id": law_id,
        "law_title": law_title,
        "source": source,
        # Numeric order, not string order. This list is the table of contents on
        # /law/<lawId> and the only crawl path to these pages; sorting slugs as
        # strings puts 刑法第3条 after 第241条.
        "articles": [pages[n] for n in sorted(pages, key=_num_sort_key)],
    }


def validate_articles(doc: dict) -> list[str]:
    """Everything that must hold before anything is written."""
    errors = []
    source = doc.get("source") or {}
    for key in ("asof", "fetched_at", "law_revision_id", "amendment_enforcement_date"):
        if not source.get(key):
            errors.append(f"source.{key} is missing")
    if source.get("asof") and source.get("fetched_at"):
        if not source["fetched_at"].startswith(source["asof"]):
            errors.append("source.asof and source.fetched_at are different days")
    if source.get("amendment_enforcement_date") and source.get("asof"):
        if source["amendment_enforcement_date"] > source["asof"]:
            errors.append("source.amendment_enforcement_date is after the asof")

    pages = doc.get("articles") or []
    if not pages:
        errors.append("articles is empty")

    seen = set()
    for page in pages:
        num = page.get("article_num", "?")
        slug = page.get("slug", "")
        if not _SLUG_RE.match(slug):
            errors.append(f"{num}: slug {slug!r} is not in the canonical form")
        if slug in seen:
            errors.append(f"{num}: duplicate slug {slug!r}")
        seen.add(slug)
        if page.get("current", {}).get("status") not in ("present", "merged_deleted"):
            errors.append(f"{num}: unknown current.status")
        text = "".join(p.get("text", "") for p in page.get("current", {}).get("paragraphs", []))
        if not text.strip():
            errors.append(f"{num}: current text is empty")
        if not (page.get("label") or "").strip():
            errors.append(f"{num}: no label in today's text")
        if not page.get("changes"):
            errors.append(f"{num}: no changes")
        for change in page.get("changes", []):
            if not (change.get("change_description") or "").strip():
                errors.append(f"{num}: a change has no description")
        if page.get("current", {}).get("status") == "merged_deleted" and not page.get("former"):
            errors.append(f"{num}: a deleted article has no former text")
    return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（44 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): 法令単位 JSON の構築と保存前検証"
```

---

## Task 7: main() — 取得・JST の番兵・全法令そろってから原子的に保存

**Files:**
- Modify: `scripts/articles.py`
- Test: `tests/test_articles.py`

**Interfaces:**
- Consumes: Task 1〜6
- Produces: `main()`、`DATA_DIR`、`FRONTEND_DIR`、`JST`、`shipped_diff_docs(data_dir) -> dict[str, list[dict]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_articles.py に追記
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_articles.py -v -k 'main or no_main_text'`
Expected: FAIL — `AttributeError: module 'articles' has no attribute 'main'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/articles.py の import に追記
import datetime
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from fetch import fetch_law_data

JST = ZoneInfo("Asia/Tokyo")
DATA_DIR = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"

# <lawId>_<YYYY-MM-DD>_<YYYY-MM-DD>.json
_DIFF_NAME = re.compile(r"^([0-9A-Z]+)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")


def shipped_diff_docs(data_dir: Path) -> dict[str, list[dict]]:
    """law_id -> its shipped diff documents, each tagged with its diff_id."""
    by_law: dict[str, list[dict]] = {}
    for path in sorted(data_dir.glob("*.json")):
        m = _DIFF_NAME.match(path.name)
        if not m:
            continue
        doc = json.loads(path.read_text())
        doc["_diff_id"] = path.stem
        by_law.setdefault(m.group(1), []).append(doc)
    return by_law


def _write_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload)
    os.replace(tmp, path)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    by_law = shipped_diff_docs(FRONTEND_DIR)
    law_ids = args or sorted(by_law)

    today = datetime.datetime.now(JST).date().isoformat()
    built: dict[str, dict] = {}

    for law_id in law_ids:
        docs = by_law.get(law_id)
        if not docs:
            print(f"{law_id}: no shipped diff; skipping")
            continue
        changes = collect_changes(docs, today)
        if not changes:
            # 労働基準法 has only 附則 changes. Nothing to build, nothing wrong.
            print(f"{law_id}: no 本則 change; no file")
            continue
        print(f"{law_id}: fetching today's text ({len(changes)} articles)")
        # There is deliberately no older file to fall back to: falling back is
        # how the text silently goes stale. Exit rather than let the exception
        # out, so a caller can tell "the fetch failed" (4) from "the data is
        # wrong" (2) and "the day changed" (3).
        try:
            document = fetch_law_data(law_id, today)
        except httpx.HTTPError as exc:
            print(f"  error: fetching {law_id} failed: {exc}")
            sys.exit(4)
        law_full_text = document.get("law_full_text")
        if not law_full_text:
            print(f"  error: {law_id}: the API returned no law_full_text for asof {today}")
            sys.exit(4)
        revision = document.get("revision_info") or {}

        fetched_at = datetime.datetime.now(JST).replace(microsecond=0)
        # Midnight between deciding the asof and holding the text. Checked here
        # rather than only before saving, so the run stops at the first law that
        # crossed it -- and so this never reaches validate_articles, which would
        # report it as "asof and fetched_at are different days" (exit 2) and
        # bury the one thing the caller needs to know.
        if fetched_at.date().isoformat() != today:
            print(
                f"The JST date changed during generation ({today} -> "
                f"{fetched_at.date().isoformat()}); not saving."
            )
            sys.exit(3)

        # The law's name as of today, not as of the shipped diff. 情プラ法
        # (413AC0000000137) was renamed: the diffs still say 特定電気通信役務提供者
        # の損害賠償責任の制限…, today's revision_info and the site's own /law page
        # say 特定電気通信による情報の流通によって発生する権利侵害等への対処…. A page
        # headed "現在の条文（取得日時点）" must not carry the pre-rename name.
        law_title = (revision.get("law_title") or "").strip()
        if not law_title:
            print(f"  error: {law_id}: revision_info carries no law_title")
            sys.exit(4)

        source = {
            "asof": today,
            "fetched_at": fetched_at.isoformat(),
            "law_revision_id": revision.get("law_revision_id", ""),
            "amendment_enforcement_date": revision.get("amendment_enforcement_date", ""),
        }
        doc = build_law_articles(law_id, law_title, changes, law_full_text, source)
        errors = validate_articles(doc)
        if errors:
            for e in errors:
                print(f"  error: {e}")
            sys.exit(2)
        built[law_id] = doc

    # Nothing is published until every requested law has been built and checked.
    if datetime.datetime.now(JST).date().isoformat() != today:
        print(
            f"The JST date changed during generation ({today} -> "
            f"{datetime.datetime.now(JST).date().isoformat()}); not saving."
        )
        sys.exit(3)

    for law_id, doc in built.items():
        payload = json.dumps(doc, ensure_ascii=False, indent=2)
        _write_atomic(DATA_DIR / "articles" / f"{law_id}.json", payload)
        _write_atomic(FRONTEND_DIR / "articles" / f"{law_id}.json", payload)
        print(f"  -> {law_id}: {len(doc['articles'])} articles")

    # A law that drops to zero target articles leaves its previous file behind,
    # and the stale copy keeps shipping pages the diffs no longer support.
    if not args:
        for directory in (DATA_DIR / "articles", FRONTEND_DIR / "articles"):
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                if path.stem not in built:
                    print(f"  removing stale {path.name}")
                    path.unlink()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_articles.py -v`
Expected: PASS（50 件）

- [ ] **Step 5: Commit**

```bash
git add scripts/articles.py tests/test_articles.py
git commit -m "feat(articles): main を足す（取得失敗で止まる・日付が変わったら保存しない）"
```

---

## Task 8: 実データを生成し、出荷データ検査を足す

**Files:**
- Modify: `tests/test_shipped_data.py`, `.gitignore`, `CLAUDE.md`
- Create: `frontend/public/data/articles/*.json`（生成物）

**Interfaces:**
- Consumes: Task 7 の `main()`
- Produces: 出荷済み `articles/*.json`

- [ ] **Step 1: `.gitignore` と CLAUDE.md を直す**

```bash
printf 'data/articles/\n' >> .gitignore
```

`CLAUDE.md` の Project Structure にある `data/` の行を直す（「all subdirs gitignored」は列挙式なので維持できる）。`scripts/` の一覧に 1 行足す:

```
│   ├── articles.py        Per-article pages (current text + this article's history)
```

- [ ] **Step 2: Write the failing shipped-data tests**

```python
# tests/test_shipped_data.py に追記
import datetime
import json
from pathlib import Path

import pytest

ARTICLES_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data" / "articles"


def shipped_articles():
    return sorted(ARTICLES_DIR.glob("*.json"))


def test_shipped_article_files_are_present():
    # Without this, every test below passes vacuously on an empty glob.
    assert len(shipped_articles()) >= 1


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_shipped_articles_pass_validate_articles(path):
    import articles

    assert articles.validate_articles(json.loads(path.read_text())) == []


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_shipped_article_source_records_one_run(path):
    source = json.loads(path.read_text())["source"]
    fetched = datetime.datetime.fromisoformat(source["fetched_at"])
    assert fetched.tzinfo is not None
    assert fetched.utcoffset() == datetime.timedelta(hours=9)
    assert fetched.date().isoformat() == source["asof"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_shipped_summary_means_the_text_still_matched(path):
    """The version gate, re-run on the bytes that ship.

    Checking only for abolished penalty names would let 著作権法122条の2 through:
    its note is about 秘密保持命令 while today's article is about 帳簿, and
    neither string contains a penalty name. The comparison has to be the same
    one the generator made, so it is made again here from the shipped diffs.
    """
    import articles

    doc = json.loads(path.read_text())
    docs = articles.shipped_diff_docs(ARTICLES_DIR.parent)[doc["law_id"]]
    changes = articles.collect_changes(docs, doc["source"]["asof"])
    for page in doc["articles"]:
        if page["current_summary"] is None:
            continue
        latest = changes[page["article_num"]][0]
        current = page["current"]["paragraphs"]
        assert articles.texts_match(latest["paragraphs_after"], current), page["article_num"]
        text = "".join(p["text"] for p in current)
        assert articles.summary_is_safe(page["current_summary"]["text"], text), page["article_num"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_shipped_deleted_article_carries_its_former_text(path):
    # validate_articles checks former only when status is merged_deleted, so a
    # deleted article shipped as `present` would slip through. Pin it on the
    # bytes: every page whose newest change is a deletion must be a tombstone.
    doc = json.loads(path.read_text())
    for page in doc["articles"]:
        if page["changes"][0]["type"] != "deleted":
            continue
        assert page["current"]["status"] == "merged_deleted", page["article_num"]
        assert page["former"] and page["former"]["paragraphs"], page["article_num"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_a_page_without_a_current_summary_shows_no_current_links(path):
    # spec §4: the gate covers the related-article links too, not just prose.
    doc = json.loads(path.read_text())
    for page in doc["articles"]:
        if page["current_summary"] is None:
            assert page["related_articles"] == [], page["article_num"]


@pytest.mark.parametrize("path", shipped_articles(), ids=lambda p: p.stem)
def test_shipped_articles_match_the_shipped_diffs(path):
    # The page set is derived, not a magic number.
    import articles

    doc = json.loads(path.read_text())
    docs = articles.shipped_diff_docs(ARTICLES_DIR.parent)[doc["law_id"]]
    expected = set(articles.collect_changes(docs, doc["source"]["asof"]))
    assert {p["article_num"] for p in doc["articles"]} == expected
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/test_shipped_data.py -v -k 'article'`
Expected: FAIL — `test_shipped_article_files_are_present` が `assert 0 >= 1` で落ちる

- [ ] **Step 4: 実データを生成する**

Run: `uv run python scripts/articles.py --all`
Expected: 11法令ぶんの JSON が書かれ、合計条文数が表示される。労働基準法は `no 本則 change; no file`。

**ここで `LookupError` が出たら止まる。** その条文は「施行済みの改正があるのに今日の本文に無い」ので、条番号と法令を報告して人に上げる（勝手に飛ばさない）。

- [ ] **Step 5: Run the shipped-data tests to verify they pass**

Run: `uv run pytest tests/test_shipped_data.py -v -k 'article'`
Expected: PASS

- [ ] **Step 6: 版不一致の実数を記録する**

Run:
```bash
uv run python -c "
import json, glob
pages = [p for f in glob.glob('frontend/public/data/articles/*.json') for p in json.load(open(f))['articles']]
no_summary = [p for p in pages if p['current_summary'] is None]
print(f'total {len(pages)} / summary dropped {len(no_summary)}')
for p in no_summary[:10]: print(' ', p['article_num'], p['display_num'])
"
```
Expected: 合計が出荷条文数と一致し、落ちた件数が出る（設計時の実測は162中30）。この数字を commit メッセージに残す。

- [ ] **Step 7: Commit**

```bash
git add .gitignore CLAUDE.md tests/test_shipped_data.py frontend/public/data/articles
git commit -m "feat(articles): 条文ページ用データを生成し、出荷データ検査を足す"
```

---

## Task 9: フロントエンドの型・読み出し・ページ

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/data.ts`
- Create: `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx`, `frontend/components/article-text.tsx`, `frontend/components/article-history.tsx`, `frontend/components/article-links.tsx`

**Interfaces:**
- Consumes: Task 8 の出荷済み `articles/*.json`
- Produces: `LawArticles` / `ArticlePage` 型、`getArticleLawIds()` / `getArticleData(lawId)` / `getArticleParams()` / `findArticle(lawId, slug)`

- [ ] **Step 1: 型を足す**

```typescript
// frontend/lib/types.ts に追記

export interface ArticleSource {
  asof: string;
  fetched_at: string;
  law_revision_id: string;
  amendment_enforcement_date: string;
}

/** A paragraph of today's text. `mark` is what the printed law shows in the
 *  margin ("" for the first paragraph, "２" onward); `num` is what a citation
 *  uses. Both come from the Article node, not from a position counter. */
export interface ArticleParagraph extends Paragraph {
  mark: string;
}

export interface CurrentText {
  status: "present" | "merged_deleted";
  source_article_num: string;
  source_label: string;
  paragraphs: ArticleParagraph[];
}

export interface FormerText {
  as_of: string;
  label: string;
  paragraphs: Paragraph[];
}

/** Present only when the article's text has not moved on since the note was
 *  written. null is the normal outcome for an article amended again since. */
export interface CurrentSummary {
  text: string;
  evidence_date: string;
}

export interface ArticleChange {
  diff_id: string;
  enforcement_date: string;
  year: string;
  type: "added" | "modified" | "deleted";
  amendment_law_title: string;
  change_description: string;
  plain_summary: string;
  /** Shown as text on the history card, never as links: a reference written
   *  about an older version of this article may point at a moved provision. */
  cross_references: { ref: string; context: string }[];
}

export interface RelatedArticle {
  ref: string;
  article_num: string;
  context: string;
  slug: string | null;
  has_page: boolean;
}

export interface ArticlePage {
  article_num: string;
  slug: string;
  display_num: string;
  label: string;
  caption: string;
  section_path: string[];
  current: CurrentText;
  current_summary: CurrentSummary | null;
  former: FormerText | null;
  changes: ArticleChange[];
  related_articles: RelatedArticle[];
}

export interface LawArticles {
  law_id: string;
  law_title: string;
  source: ArticleSource;
  articles: ArticlePage[];
}
```

- [ ] **Step 2: 読み出しを足す**

```typescript
// frontend/lib/data.ts に追記
import { ArticlePage, LawArticles } from "./types";

const ARTICLE_DIR = path.join(DATA_DIR, "articles");

export function getArticleLawIds(): string[] {
  if (!fs.existsSync(ARTICLE_DIR)) return [];
  return fs
    .readdirSync(ARTICLE_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(".json", ""));
}

export function getArticleData(lawId: string): LawArticles {
  const raw = fs.readFileSync(path.join(ARTICLE_DIR, `${lawId}.json`), "utf-8");
  return JSON.parse(raw) as LawArticles;
}

/** Every (lawId, articleSlug) that ships. The slug is read, never derived:
 *  article numbers are interpreted in Python and nowhere else. */
export function getArticleParams(): { lawId: string; articleSlug: string }[] {
  return getArticleLawIds().flatMap((lawId) =>
    getArticleData(lawId).articles.map((a) => ({ lawId, articleSlug: a.slug }))
  );
}

export function findArticle(lawId: string, slug: string): ArticlePage | null {
  return getArticleData(lawId).articles.find((a) => a.slug === slug) ?? null;
}
```

- [ ] **Step 3: 検査: `getDiffIds()` が `articles/` を拾わないことを確認する**

Run: `cd frontend && npx tsc --noEmit`
Expected: エラーなし。`getDiffIds()` は `DATA_DIR` 直下の `.json` だけを読むので、サブディレクトリは `f.endsWith(".json")` で落ちる（既存の `timelines/` と同じ）。

- [ ] **Step 4: コンポーネントを作る**

```tsx
// frontend/lib/format.ts
/** "2026-09-22" -> "2026年9月22日".
 *
 * Built from the string rather than through Date: a date-only string parses as
 * UTC midnight, so a build running west of Greenwich would render the day
 * before -- and the day is the whole claim this page makes about its text.
 */
export function jpDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${Number(y)}年${Number(m)}月${Number(d)}日`;
}
```

```tsx
// frontend/components/article-text.tsx
import { CurrentText, FormerText } from "@/lib/types";
import { jpDate } from "@/lib/format";
// FormerText keeps the plain Paragraph shape: it comes from the shipped diff,
// which has no margin marks.

export function ArticleText({
  current,
  asof,
  displayNum,
}: {
  current: CurrentText;
  asof: string;
  displayNum: string;
}) {
  return (
    <section className="border border-[var(--border)] rounded-lg p-4">
      {/* Never "現在の条文" alone: this is a static page and the law moves. */}
      <h2 className="text-[14px] font-bold mb-3">現在の条文（{jpDate(asof)}時点）</h2>
      {current.status === "merged_deleted" && (
        <p className="mb-3 text-[13px] opacity-70">
          {displayNum}は「{current.source_label}」として欠番になっています。
        </p>
      )}
      {current.paragraphs.map((p) => (
        <p key={p.num} className="whitespace-pre-wrap leading-[26px]">
          {/* The margin number the printed law carries. Without it 民法772条
              reads as four unnumbered blocks and 第2項 cannot be located. */}
          {p.mark && <span className="mr-2 opacity-70">{p.mark}</span>}
          {p.text}
        </p>
      ))}
    </section>
  );
}

export function FormerArticleText({ former }: { former: FormerText }) {
  return (
    <section className="border border-[var(--border)] bg-[var(--muted)] rounded-lg p-4">
      {/* "削除される前の条文" is wrong for 民法753条, whose previous text was
          already the word 削除 -- what this amendment removed was the empty
          slot itself. The spec's wording says only what we know: the text as it
          stood immediately before this amendment. */}
      <h2 className="text-[14px] font-bold mb-1">
        今回の改正直前の条文（{jpDate(former.as_of)}時点）
      </h2>
      <p className="mb-3 text-[13px] opacity-70">現行法ではありません。</p>
      {former.paragraphs.map((p) => (
        <p key={p.num} className="whitespace-pre-wrap leading-[26px]">
          {p.text}
        </p>
      ))}
    </section>
  );
}
```

```tsx
// frontend/components/article-history.tsx
import Link from "next/link";
import { ArticleChange } from "@/lib/types";
import { jpDate } from "@/lib/format";

export function ArticleHistory({
  changes,
  anchor,
}: {
  changes: ArticleChange[];
  /** The article_num, which is the id the /diff card carries. */
  anchor: string;
}) {
  return (
    <section>
      <h2 className="text-[14px] font-bold mb-3">この条文の改正履歴</h2>
      <ol className="flex flex-col gap-4">
        {changes.map((c) => (
          <li
            key={c.diff_id + c.enforcement_date}
            className="border border-[var(--border)] rounded-lg p-4"
          >
            <p className="text-[13px] opacity-70">
              {jpDate(c.enforcement_date)}施行・{c.amendment_law_title}
            </p>
            <p className="mt-2 whitespace-pre-wrap leading-[26px]">{c.change_description}</p>
            {c.plain_summary && (
              // A deleted article has no text just after the amendment -- the
              // note describes what stood there just before. 民法754条's
              // paragraphs_after is empty (measured), so "改正直後" would label
              // a description of the repealed rule as a description of 削除.
              <p className="mt-2 text-[13px] opacity-70">
                {jpDate(c.enforcement_date)}
                {c.type === "deleted" ? "改正直前" : "改正直後"}の条文についての説明:{" "}
                {c.plain_summary}
              </p>
            )}
            {c.cross_references.length > 0 && (
              // Text, not links: a reference written about an older version of
              // this article may point at a provision that has since moved.
              <p className="mt-2 text-[13px] opacity-70">
                当時の関連条文: {c.cross_references.map((r) => r.ref).join("、")}
              </p>
            )}
            <Link
              href={`/diff/${c.diff_id}#${anchor}`}
              className="mt-2 inline-block text-[13px] text-[var(--diff-hunk-text)]"
            >
              この改正の全体を見る →
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
```

```tsx
// frontend/components/article-links.tsx
import Link from "next/link";
import { RelatedArticle } from "@/lib/types";

export function ArticleLinks({
  lawId,
  related,
}: {
  lawId: string;
  related: RelatedArticle[];
}) {
  if (related.length === 0) return null;
  return (
    <section>
      <h2 className="text-[14px] font-bold mb-3">関連する条文</h2>
      <ul className="flex flex-col gap-2">
        {related.map((r, i) => (
          <li key={`${r.ref}-${i}`} className="text-[13px]">
            {r.has_page && r.slug ? (
              <Link
                href={`/law/${lawId}/article/${r.slug}`}
                className="text-[var(--diff-hunk-text)]"
              >
                {r.ref}
              </Link>
            ) : (
              <span>{r.ref}</span>
            )}
            <span className="ml-2 opacity-70">{r.context}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 5: ページ本体を作る**

```tsx
// frontend/app/law/[lawId]/article/[articleSlug]/page.tsx
import type { Metadata } from "next";
import Link from "next/link";
import { getArticleParams, getArticleData, findArticle } from "@/lib/data";
import { ArticleText, FormerArticleText } from "@/components/article-text";
import { ArticleHistory } from "@/components/article-history";
import { ArticleLinks } from "@/components/article-links";
import { BreadcrumbJsonLd } from "@/components/breadcrumb-jsonld";
import { jpDate } from "@/lib/format";

export function generateStaticParams() {
  const params = getArticleParams();
  // The build is the only feedback that reaches anyone here, so make it fail.
  const seen = new Set(params.map((p) => `${p.lawId}/${p.articleSlug}`));
  if (params.length === 0 || seen.size !== params.length) {
    throw new Error(`article params are empty or contain duplicates (${params.length})`);
  }
  return params;
}

/** "民法第306条（一般の先取特権）", or without the parenthesis when the current
 *  text carries no caption -- 民法754条 has none, and an empty （） is worse
 *  than no caption at all. */
function head(lawTitle: string, displayNum: string, caption: string): string {
  return caption ? `${lawTitle}${displayNum}（${caption}）` : `${lawTitle}${displayNum}`;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lawId: string; articleSlug: string }>;
}): Promise<Metadata> {
  const { lawId, articleSlug } = await params;
  const data = getArticleData(lawId);
  const article = findArticle(lawId, articleSlug)!;
  const title = head(data.law_title, article.display_num, article.caption);
  const years = [...new Set(article.changes.map((c) => c.year))].join("・");
  // Only what every page actually carries: the dated text and the amendment
  // years we hold. "改正前後の条文" is true of deleted articles alone, and the
  // related-article links are absent on a page whose text has moved on.
  return {
    title: `${title}の条文と改正（${years}年改正）`,
    description: `${title}の${jpDate(data.source.asof)}時点の条文と、${years}年の改正内容。`,
    alternates: { canonical: `/law/${lawId}/article/${articleSlug}` },
  };
}

export default async function ArticlePageRoute({
  params,
}: {
  params: Promise<{ lawId: string; articleSlug: string }>;
}) {
  const { lawId, articleSlug } = await params;
  const data = getArticleData(lawId);
  const article = findArticle(lawId, articleSlug)!;
  const title = head(data.law_title, article.display_num, article.caption);

  return (
    <div className="flex flex-col gap-6">
      <BreadcrumbJsonLd
        items={[
          { name: "lexdiff", url: "https://lexdiff.com" },
          { name: data.law_title, url: `https://lexdiff.com/law/${lawId}` },
          {
            name: article.display_num,
            url: `https://lexdiff.com/law/${lawId}/article/${articleSlug}`,
          },
        ]}
      />
      <header>
        <h1 className="text-2xl font-bold">{title}</h1>
        {article.section_path.length > 0 && (
          <p className="mt-1 text-[13px] opacity-70">{article.section_path.join(" › ")}</p>
        )}
      </header>

      <ArticleText
        current={article.current}
        asof={data.source.asof}
        displayNum={article.display_num}
      />

      {/* spec §8 order: the current text, then what it is about, then the text
          it replaced. The "未収録" notice has to sit with the current text it
          is about, not after a block of repealed wording. */}
      <section>
        <h2 className="text-[14px] font-bold mb-2">この条文は何をする条文か</h2>
        {article.current_summary ? (
          <p className="leading-[26px]">{article.current_summary.text}</p>
        ) : (
          <p className="text-[13px] opacity-70">
            現行本文に対応する解説は未収録です。収録済み改正時点の説明は改正履歴で確認できます。
          </p>
        )}
      </section>

      {article.former && <FormerArticleText former={article.former} />}

      <ArticleHistory changes={article.changes} anchor={article.article_num} />
      <ArticleLinks lawId={lawId} related={article.related_articles} />

      <Link href={`/law/${lawId}`} className="text-[var(--diff-hunk-text)]">
        {data.law_title}の改正履歴をすべて見る →
      </Link>
    </div>
  );
}
```

- [ ] **Step 6: ビルドして確認する**

Run: `cd frontend && npm run lint && npm run build`
Expected: 成功。条文ページが静的生成される。

Run:
```bash
cd frontend && find out -path '*/article/*' -name '*.html' | wc -l
python3 -c "
import json, glob
print(sum(len(json.load(open(f))['articles']) for f in glob.glob('public/data/articles/*.json')))
"
```
Expected: **2つの数が一致する**（固定値は書かない）。

- [ ] **Step 7: Commit**

```bash
git add frontend/lib frontend/app/law frontend/components
git commit -m "feat(articles): 条文ページのルートとコンポーネントを足す"
```

---

## Task 10: 内部リンクと sitemap

**Files:**
- Modify: `frontend/app/law/[lawId]/page.tsx`, `frontend/components/diff-viewer.tsx`, `frontend/app/diff/[diffId]/page.tsx`, `frontend/app/sitemap.ts`

**Interfaces:**
- Consumes: Task 9 の `getArticleData` / `getArticleParams`
- Produces: なし（導線のみ）

**なぜこのタスクがあるか**: これが無いと163ページは孤児になり、8週後の判定が「仮説が外れた」なのか「クロールされなかった」なのか区別できなくなる。

- [ ] **Step 1: `/law/<lawId>` に条文一覧を足す**

`frontend/app/law/[lawId]/page.tsx` に、章節（`section_path[0]`）でグループ化した「改正された条文」ブロックを追加する。**中間ページは作らない。**

```tsx
// frontend/app/law/[lawId]/page.tsx に追記（既存 import に足す）
import { getArticleLawIds, getArticleData } from "@/lib/data";

/** The chapter an article sits in, with everything above it, as one key.
 *
 * section_path has no fixed depth. 民法 and 刑法 put 編 at [0] and 章 at [1];
 * the other laws put 章 at [0] and 節 at [1]. Keying on [1] therefore files
 * 道路交通法's 第18条 (第三章　車両及び路面電車の交通方法) and its 第125条
 * (第九章　反則行為に関する処理手続の特例) under one 「第一節　通則」 -- measured.
 * Find the 章 by its word rather than by position, and keep the path above it
 * in the key so two chapters that share a name never merge.
 */
function chapterKey(sectionPath: string[]): string {
  const i = sectionPath.findIndex((s) => /^第.+章/.test(s));
  return i >= 0 ? sectionPath.slice(0, i + 1).join(" › ") : sectionPath[0] ?? "";
}

// ページ本体の中で
const hasArticles = getArticleLawIds().includes(lawId);
const articleData = hasArticles ? getArticleData(lawId) : null;

// JSX に足す
{articleData && (
  <section>
    <h2 className="mb-3 text-lg font-bold">改正された条文</h2>
    {Object.entries(
      articleData.articles.reduce<Record<string, typeof articleData.articles>>((acc, a) => {
        (acc[chapterKey(a.section_path)] ||= []).push(a);
        return acc;
      }, {})
    ).map(([section, items]) => (
      <div key={section} className="mb-4">
        {section && (
          <h3 className="mb-2 text-[13px] opacity-70">{section.split(" › ").pop()}</h3>
        )}
        <ul className="flex flex-wrap gap-x-4 gap-y-1">
          {items.map((a) => (
            <li key={a.slug}>
              <Link
                href={`/law/${lawId}/article/${a.slug}`}
                className="text-[var(--diff-hunk-text)]"
              >
                {a.display_num}
                {a.caption && `（${a.caption}）`}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    ))}
  </section>
)}
```

- [ ] **Step 2: `/diff` の各本則カードに anchor とリンクを足す**

`frontend/components/diff-viewer.tsx` の条文カードに `id={diff.article_num}` を足し、見出しから条文ページへリンクする。**レイアウトと本文は変えない。** `lawId` と、ページを持つ条番号の集合を props で受け取る（`DiffViewer` は今 `lawId` を持っていないので追加が要る）。

```tsx
// diff-viewer.tsx の props
export function DiffViewer({
  diffs,
  lawId,
  articleSlugs,
}: {
  diffs: ArticleDiff[];
  lawId: string;
  articleSlugs: Record<string, string>;  // article_num -> slug
}) {
```

条文カードの見出し部分:

```tsx
{/* id on the card itself: this is what /article links back to with a hash. */}
<div id={diff.article_num} className="scroll-mt-4">
  <button /* 既存の展開ボタン。中身は変えない */ />
  {articleSlugs[diff.article_num] && (
    // Outside the button, so a click goes to the page and not also to the
    // expand toggle.
    <Link
      href={`/law/${lawId}/article/${articleSlugs[diff.article_num]}`}
      className="ml-2 text-[13px] text-[var(--diff-hunk-text)]"
    >
      この条文のページ →
    </Link>
  )}
</div>
```

`frontend/app/diff/[diffId]/page.tsx` の呼び出し側で `articleSlugs` を組み立てて渡す。
**`getArticleData` を無条件に呼ばない** — 労働基準法は本則の改正が 0 件で `articles/` の
ファイルを持たないため、`readFileSync` で落ちて附則だけの diff 2 本のビルドが止まる。

```tsx
// frontend/app/diff/[diffId]/page.tsx
const articleSlugs: Record<string, string> = getArticleLawIds().includes(data.law_id)
  ? Object.fromEntries(getArticleData(data.law_id).articles.map((a) => [a.article_num, a.slug]))
  : {};
```

**`id` はカードの外側に付け、`Link` は既存の展開ボタンの外に置く。** 既存の見出しは
展開用の `<button>` なので、その中に `Link` を入れるとボタンの中のリンクになり、
クリックが展開と遷移の両方に掛かる（入れ子として不正でもある）。

- [ ] **Step 3: sitemap に足す**

```tsx
// frontend/app/sitemap.ts に追記
import { getArticleLawIds, getArticleData } from "@/lib/data";

// entries に足す
...getArticleLawIds().flatMap((lawId) => {
  const data = getArticleData(lawId);
  return data.articles.map((a) => ({
    url: `https://lexdiff.com/law/${lawId}/article/${a.slug}`,
    lastModified: data.source.asof,
    priority: 0.7,
  }));
}),
```

- [ ] **Step 4: ビルドして導線を確認する**

Run: `cd frontend && npm run lint && npm run build`
Expected: 成功。

Run:
```bash
cd frontend && grep -c 'article/' out/law/129AC0000000089.html
grep -c 'law/129AC0000000089/article/' out/sitemap.xml
```
Expected: 法令ページに条文ページへのリンクが複数あり、sitemap にも条文 URL が並ぶ。

- [ ] **Step 5: Commit**

```bash
git add frontend/app frontend/components
git commit -m "feat(articles): 法令ページ・差分ページ・sitemap から条文ページへの導線を足す"
```

---

## 受け入れコマンド（全タスク完了後に通しで走らせる）

```bash
uv run pytest
uv run python scripts/articles.py --all
uv run pytest tests/test_shipped_data.py
cd frontend && npm run lint
cd frontend && npm run build
```

最後に、生成 JSON の条文数と静的生成された HTML 数が一致することを確認する:

```bash
cd frontend
find out -path '*/article/*' -name '*.html' | wc -l
python3 -c "
import json, glob
print(sum(len(json.load(open(f))['articles']) for f in glob.glob('public/data/articles/*.json')))
"
```

---

## Self-Review

**1. Spec coverage**

| spec の節 | 実装するタスク |
|---|---|
| §1 対象と URL | Task 1（slug）・Task 2（対象の絞り込み）・Task 9（`generateStaticParams`） |
| §2 生成スクリプト | Task 1〜7 |
| §3 取得と保存の原子性 | Task 7 |
| §4 版整合ゲート | Task 4（判定）・Task 6（適用）・Task 8（出荷データ検査） |
| §5 出力データ | Task 6 |
| §6 範囲ノードと削除条文 | Task 2（diff 側）・Task 3（現行法側）・Task 6（`former`） |
| §7 cross references | Task 5 |
| §8 フロントエンド | Task 9 |
| §9 metadata / canonical / 重複 | Task 9（metadata・canonical）・Task 10（内部リンク・sitemap） |
| §10 検証 | Task 1〜7 の各テスト・Task 8 の出荷データ検査 |
| §11 仮説検証 | 実装対象ではない（8週後の観測。spec §11 に手順がある） |
| §13 別 issue | 実装対象ではない |

**未カバー**: spec §9 の「`/diff` の履歴カードから `/diff#anchor` へ戻れるようにする」は Task 10 Step 2 の anchor 付与で足りる。spec §3 の `.gitignore` は Task 8 Step 1。

**2. Placeholder scan**: 「適切なエラー処理を足す」「エッジケースを扱う」「Task N と同様」の類は無い。すべてのコードステップに実コードがある。

**3. Type consistency**:
- Python: `collect_changes` が返すキー（`diff_id` / `enforcement_date` / `plain_summary` / `paragraphs_after` / `title_before` / `date_before`）を Task 6 の `build_law_articles` がそのまま使う。
- `resolve_current` は `status` / `source_article_num` / `source_label` / `caption` / `paragraphs` を返し、Task 6 が全部読む。
- TS: `ArticlePage.current_summary` は `CurrentSummary | null`。ページ本体は null 分岐を持つ。
- TS: `RelatedArticle.slug` は `string | null`、`has_page` と組で使う。
- `articleSlug` という TS 関数は**存在しない**（Global Constraints のとおり）。`slug` は JSON から読むだけ。


---

## Gate 2 の記録（周回1）

レビュワー: grok（異族。`claude-external-design --mode critique --tool grok --sandbox none`。
このホストでは Landlock が無くサンドボックスが適用できないため、無防備であることを
明示して実行した — wharfe/dotfiles#173）。出力は `docs/design-debate/article-pages/gate2-grok.md`。

指摘は「重要」9件・「軽微」5件。**全件を親セッションが実測で確認し、全件を直した。**

| # | 指摘 | 直した場所 |
|---|---|---|
| 1 | 版が不一致でも `related_articles` を現行のリンクとして出す（spec §4 違反）。不一致32条のうち29条が参照を持ち、計144行 | Task 6: `current_summary` が `null` なら `_refs` を空にする。`changes[]` に `cross_references` を足し、履歴カードでテキスト表示 |
| 2 | 別名の先頭一致で短い条名が長い条名を食う。民法は `778 / 778_2 / 778_3 / 778_4` が同居（実測） | Task 5: 最長一致 + 「の」+漢数字で続く場合は親へリンクしない境界規則。テスト2本追加 |
| 3 | slug の文字列ソートが目次になる。刑法は `176…241, 3, 3-2` の順（実測） | Task 6: `_num_sort_key` で数値順 |
| 4 | 出荷検査が名前と違い本文一致を見ていない。著作権法122条の2 は刑名を含まないので素通りする | Task 8: 出荷 diff から `texts_match` をやり直す。`related_articles` の空も検査 |
| 5 | **Task 7 の計画は自己矛盾** — `main()` は例外を投げるのにテストは `SystemExit` を期待。日付テストは `validate_articles` が先に exit 2 を出して exit 3 に届かない | Task 7: 取得失敗と本文欠落を exit 4、JST の番兵を `fetched_at` 生成直後へ移動 |
| 6 | 削除条文の見出しが 753条で逆の意味になる（`paragraphs_before` が既に「削除」）。表示順も spec §8 と違う | Task 9: 見出しを「今回の改正直前の条文」に。順序を 現在の条文 → 説明 → 改正直前 → 履歴 へ |
| 7 | 戻りリンクに `#条番号` が無く、`id` を `<button>` の中に置くと展開と遷移が両方走る | Task 9/10: `href` にアンカー、`id` はカード外側、`Link` はボタンの外 |
| 8 | 労働基準法は `articles/` のファイルを持たないので `getArticleData` が落ち、ビルドが止まる | Task 10: `getArticleLawIds().includes()` で守る |
| 9 | ダークモードで「未収録です」が背景に溶ける。既存は `--foreground` / `--border` / `--muted` に乗っている | Task 9: 全コンポーネントを `border-[var(--border)]` / `bg-[var(--muted)]` / `opacity-70` へ |
| 10 | description が「改正前後の条文、関連する条文へのリンクを掲載」と、無いものを載せたと言う | Task 9: 取得日時点の条文と改正年だけに |
| 軽 | `-k` がクォートされておらずシェルの `or` で切れる | 全 Run 行をクォート |
| 軽 | `new Date("2026-09-22")` は UTC 午前0時。UTC 以西でビルドすると「時点」が1日ずれる | `frontend/lib/format.ts` の `jpDate()` を新設し、文字列から組む |
| 軽 | 対象0件になった法令の古い `articles/<lawId>.json` が残る | Task 7: `--all` のとき、今回作らなかったファイルを消す。テスト追加 |
| 軽 | 一覧のグループが `section_path[0]` だけなので民法の親族編36本が一段になる | Task 10: `section_path[1] ?? [0]`（編ではなく章） |
| 軽 | `extract_text` がルビの読みを連結する（「失踪そうの宣告」） | Task 3: `_text_without_ruby()` を caption に適用。テスト追加 |

### spec 側の訂正

grok の「確認したいこと」から、**spec §6 の根拠例が事実に反していた**ことが判明した。
R1 の批評が「育児介護休業法の `36:52` は17条ぶんの実体を覆う」と書き、それが spec に入っていたが、
実測では今日の本文は「第三十六条から第五十二条まで削除」で、`elm=Article_40` は 400 を返す
（個別ノードは存在しない）＝これも欠番の範囲だった。
**判定規則そのものは正しく倒れる**（本文が「削除」なので `merged_deleted` になり、それが正解）が、
根拠が偽だと後から誰かが例を見て規則を「直して」しまうので、`spec.md` §6 に訂正を残した。


## Gate 2 の記録（周回2）

同じレビュワー（grok）に改訂版を当てた。1回目は 900s で timeout（exit 3、出力 0 バイト）。
規則どおり**同じツールを1回だけ `--timeout 1800` で再試行**し、完走した。
出力は `docs/design-debate/article-pages/gate2-grok-r2.md`。

レビュワーは先に「実データでページを生成できる」ことを確認している（2026-09-08 のスナップショットで
対象163件が `present` 161 + `merged_deleted` 2、未解決 0。本文と `paragraphs_after` は163件すべて一致）。

| 段階 | 指摘 | 直した場所 |
|---|---|---|
| **critical** | ページの法令名を今日の取得ではなく出荷 diff から取っている。`413AC0000000137` は改名済みで、約23枚が旧称になる（実測で両方の値を確認） | Task 7: `revision_info.law_title` を使い、空なら exit 4。テスト2本追加 |
| important | `section_path[1] ?? [0]` は「章」ではない。民法・刑法は `[0]`=編 `[1]`=章、他は `[0]`=章 `[1]`=節。道交法は「第一節　通則」に第三章と第九章が混ざる（実測） | Task 10: `chapterKey()` で「章」を語で探し、上位パスごとキーにする |
| important | 削除改正の解説に「改正直後の条文についての説明」と付くが、改正直後の本文は「削除」。民法753/754 の `paragraphs_after` は空（実測） | Task 9: `type === "deleted"` なら「改正直前」。Task 6 のテストで `paragraphs_after=[]` を固定 |
| minor | Task 3 のコメントが、末尾で撤回した `36:52` の例を実装の根拠として残している | コメントを「規則は本文に立つ、例には立たない」へ |
| minor | `_KANJI_DIGITS` に算用数字が無く、後から `display_num` を別名表に足すと `第778条の4` が親へリンクする | 算用数字（半角・全角）を追加 |
| minor | 全件原子性のテストが法令1件の失敗しか見ていない | Task 7: 2法令で、2件目が検証失敗しても1件目が出ないことを固定 |

### 周回2 で停止規則に当たった

CLAUDE.md:「**同じ根の指摘が2回**出たら、周回を使い切る前に実装ではなく spec へ戻す」。

- 周回1 の「関連条文にゲートが掛かっていない」
- 周回2 の「法令名が改名前のまま」

は**同じ根**である: このページは**年齢の違う2つの出所**から組み立てられ、フィールドごとに
鮮度の判断が要る。出てきた順に潰すと次の1つが必ず残る（本文 → 解説 → リンク → 名前、と4回続いた）。

規則が問う「目的由来か、手段由来か」は**手段由来**。よって手段ごと替えた:

1. **spec §5 に「フィールドの出所表」を追加**し、閉じた列挙にした。
   「現在」と名乗るブロックに出るものは、今日の取得由来か、ゲートを通ったものだけ。
   新しいフィールドは、表に行を足してから実装する。行が書けないものはページに出さない。
2. 表を書いたことで、**最後に残っていた過去由来の表示フィールド `section_path` が見つかった**
   （spec §12 が「残存リスク」として挙げていたもの）。`diff.find_section_path` を今日の木に
   当てて解決した。これは周回2 のレビュワーも指摘していない。

**Gate 2 の状態**: 周回2 までの指摘はすべて解消。ただし
**「手段ごと替えた後の版」はまだレビューを受けていない**。周回3 を使うかは人の判断に委ねる。


## Gate 2 の記録（周回3・上限に到達）

同じレビュワー（grok、`--timeout 1800`）に、出所表と `section_path` 変更を含む版を当てた。
出力は `docs/design-debate/article-pages/gate2-grok-r3.md`。

| 段階 | 指摘 | 対応 |
|---|---|---|
| **重要** | **項番号がデータにも画面にも残らない。** `format_paragraph` は `ParagraphNum` を読み飛ばし、計画は項番号を位置から振り直していた。民法772条は `Paragraph@Num` が `1..4`、表示用が `''、２、３、４`（実測）。複数項の改正エントリは **107件** | Task 3: `Paragraph@Num` を `num`、`ParagraphNum` を `mark` として読む。Task 4: `texts_match` が `num` も比べる（spec §4 の「段落番号と本文」どおり）。Task 9: `mark` を項の頭に出す。型に `ArticleParagraph` を追加。テスト2本 |
| **重要** | 削除条文の `section_path` が空になる。`find_section_path(tree, "753")` は `None`（753 は今日 Article ノードでない） | **周回3 の起動前に親セッションが実測で発見し、修正済み**。`current["source_article_num"]`（`753:754`）で引く。レビュワーの処方と一致 |
| **重要** | 撤回した「`36:52` は17条分の実体」が、**テストのコメント**として根拠のまま残っている（実装側コメントだけ直していた） | Task 3: テストのコメントを「合成フィクスチャ。規則は本文が削除であることに立つ、例には立たない」へ |
| 軽微 | アンダースコアを省いた参照（`7782` = `778_2`）が veto に落ち、関連リンクが黙って8件消える | Task 5: `raw_num` が `target.replace("_","")` に等しい場合も通す。`824` 対 `824_2` は落ちたまま |
| 軽微 | `label` が空のとき `title_before` に落ちる口が、出所表を閉じた後も残っている | Task 6: フォールバックを削除し、空なら `validate_articles` が落とす |
| 軽微 | 出荷検査に「削除ページは `merged_deleted` かつ `former`」が無い | Task 8: 実データの753・754を出荷 JSON 側で固定するテストを追加 |
| 軽微 | 公開はファイルごとの `os.replace` で、書き込みループ途中の死には届かない | **実装せず、保証の範囲を spec §3 に明記した**（下記） |
| 確認 | spec §4 は履歴カードを一律「改正直後の条文についての説明」としているが、計画は削除のとき「改正直前」に分岐する。どちらが正か | **spec を直した**。削除条文では「改正直後」が事実と逆（民法754条の `paragraphs_after` は空で、直後の本文は「削除」） |

### 実装しなかった1件とその理由

ディレクトリごとの入れ替えは**採らない**。`articles` → `articles.old` →
`articles.new` → `articles` の2回リネームになり、その間に死ぬとディレクトリごと消える窓が生まれる。
今の残余窓は「検証済みのファイルを数個書くミリ秒」で、そこで死んでも残るのは個別には妥当なファイルで、
再実行で揃う。**悪化させる取り替えはしない。** 保証の範囲を spec §3 に書いた。

### Gate 2 の終了状態

**周回3 で上限に到達した**（CLAUDE.md の (B) 区分・上限3）。

- 周回1〜3 の指摘は全件対応済み。未対応で残した high 以上は**無い**
- ただし **周回3 の修正そのものはレビューを受けていない**。上限に達したため、
  ここは Gate 3（実装後）で拾う
- **これを PASS とは呼ばない。** 上限による打ち切りである
