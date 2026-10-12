# 施行予定の改正の差分ページ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** e-Gov の `UnEnforced` 改正を、AI 解説なしの「施行前」diff ページとして出荷する。

**Architecture:** `diff.py` の文書組み立てを関数 `build_diff_document` に切り出し（出力不変）、
新規 `scripts/pending.py` が「取り直した改正一覧 → 前日/当日の取得 → diff → `pending` 情報の付与
→ 出荷」を AI を通さずに行う。`--check` で出荷済みの施行前 diff の鮮度を検査。フロントは
`lib/pending.ts` の 1 か所でビルド日（JST）と比べて施行前を判定する。

**Tech Stack:** Python 3.13 (uv, httpx, pytest) / Next.js App Router SSG, TypeScript strict

**Spec:** `docs/pending-amendments/spec.md`

## Global Constraints

- 施行前の判定は「施行日 > 今日（Asia/Tokyo）」。Python は `datetime.now(ZoneInfo("Asia/Tokyo"))`、フロントはビルド時の JST 日付。
- 施行日が未確定（`amendment_scheduled_enforcement_date` あり）なら `amendment_enforcement_comment` を原文のまま出し、予定日は「e-Gov 上の予定日」と添える。言い換えない。施行前ページのタイトル・説明に施行年を入れない。
- 施行前の diff に `pr_summary` / `annotation` を書かない。AI を呼ぶ経路に入れない。
- 施行済み diff の出力 JSON は 1 バイトも変えない（`pending` キーは pending.py だけが足す）。
- 出荷物の削除は人。スクリプトは消さずに報告して非ゼロで止まる。
- コメントは英語、利用者向け文言は日本語。

## Review Focus

1. 同じ日に施行予定の改正が 2 本（例: 民法 2028-12-23 と 2029-06-23 は同一改正法の別段階、他法令で同日複数がありうる）→ 1 diff に全 revision を `pending.revisions` で並べ、どれか 1 本に帰属させない。Task 2 のテスト `test_same_day_pending_revisions_are_all_listed`。
2. 施行日を過ぎたのに作り直していない施行前 diff → **閉じる側**: フロントは `pending` を持つ限り施行前として描き、「{generated_on} 時点の施行予定の情報。施行されたかは未確認」と書く。`articles.collect_changes` は `pending` を持つ diff を除外。`--check` は「施行日を過ぎた」で exit 1。Task 2 `test_check_reports_enforced`、Task 3 `test_collect_changes_skips_pending_docs`。
6. 手前の施行待ちの日付が動く／新しい改正が手前に成立する → 後ろの diff は中身だけ古くなる。`basis_revision_ids` の不一致で `--check` exit 1。Task 2 `test_check_reports_a_changed_basis`。
7. explainer で同名タイトルの施行済み diff と施行前 diff が並ぶ → 施行済みが grounded で残る。Task 3 `test_same_title_keeps_the_enforced_grounded_entry`。
3. 予定日が政令で動いた → `--check` が「日付が変わった」で exit 1。Task 2 `test_check_reports_moved_date`。
4. 表が変わる施行待ち → 出荷せず報告、他の改正の処理は続ける。Task 2 `test_tables_changed_is_withheld_and_run_continues`。
5. 年表のキャッシュが古い → pending.py が `_revisions.json` を取り直して書くので timeline.py は新しい一覧を読む。shipped テスト `test_pending_diffs_agree_with_their_timeline` が食い違いを落とす（Task 3）。

---

### Task 1: `diff.py` の文書組み立てを関数に切り出す（出力不変）

**Files:**
- Modify: `scripts/diff.py:452-` (`main`)
- Test: `tests/test_diff_document.py`（新規）

**Interfaces:**
- Produces: `build_diff_document(law_id: str, date_before: str, date_after: str, before_data: dict, after_data: dict, revisions: list[dict]) -> dict` — `main()` が今 `output` に組んでいる dict をそのまま返す。`compute_diff` の ValueError と「revision が一覧に無い」は `ValueError` で投げる。表の変化・差分ゼロの判定はしない（呼び出し側の責務。副作用＝ファイル削除を伴うため）。
- Produces: `diffs_or_none(...)` は作らない。呼び出し側は `tables_changed(...)` と `doc["diffs"]` の空判定を自分でする。

- [ ] **Step 1: 切り出し前の出力を退避する（不変条件5の基準）**

`diff.py` は `data/diffs/` を上書き・削除する（gitignore 対象で git から戻せない）。**バックアップを
ループと同じブロックの先頭で取り、取れなければ止める。** 1 回目は `OUT=baseline`、Task 1 実装後に
`OUT=after` で同じブロックを回す。

```bash
B=$TMPDIR/diffs-backup; OUT=${OUT:-baseline}; S=$TMPDIR/pending-$OUT
if [ "$OUT" = baseline ]; then rm -rf "$B" && cp -R data/diffs "$B" || exit 1; fi
rm -rf "$S"; mkdir -p "$S"
for f in frontend/public/data/*_????-??-??_????-??-??.json; do
  id=$(basename "$f" .json); law=${id%%_*}; rest=${id#*_}; b=${rest%_*}; a=${rest#*_}
  [ -f data/raw/${law}_$b.json ] && [ -f data/raw/${law}_$a.json ] || { echo "$id noraw" >> "$S/rc.txt"; continue; }
  uv run python scripts/diff.py "$law" "$b" "$a" > "$S/$id.out" 2>&1; echo "$id $?" >> "$S/rc.txt"
  [ -f "data/diffs/$id.json" ] && cp "data/diffs/$id.json" "$S/$id.json"
done
rm -rf data/diffs && cp -R "$B" data/diffs   # restore every time
```

- [ ] **Step 2: 失敗するテストを書く**

```python
# tests/test_diff_document.py
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import diff

def _law(articles_xml_children, rev_id, title="改正法", date="2026-04-01"):
    return {
        "revision_info": {"law_title": "テスト法", "law_revision_id": rev_id,
                          "amendment_law_title": title, "amendment_enforcement_date": date},
        "law_full_text": {"tag": "Law", "attr": {}, "children": [
            {"tag": "LawBody", "attr": {}, "children": [
                {"tag": "MainProvision", "attr": {}, "children": articles_xml_children}]}]},
    }

def _article(num, text):
    return {"tag": "Article", "attr": {"Num": num}, "children": [
        {"tag": "ArticleTitle", "attr": {}, "children": [f"第{num}条"]},
        {"tag": "Paragraph", "attr": {"Num": "1"}, "children": [
            {"tag": "ParagraphSentence", "attr": {}, "children": [
                {"tag": "Sentence", "attr": {}, "children": [text]}]}]}]}

def test_build_diff_document_names_the_revision():
    before = _law([_article("1", "旧")], "X_20260331")
    after = _law([_article("1", "新")], "X_20260401")
    revs = [{"law_revision_id": "X_20260401", "amendment_law_title": "改正法",
             "amendment_enforcement_date": "2026-04-01"}]
    doc = diff.build_diff_document("X", "2026-03-31", "2026-04-01", before, after, revs)
    assert doc["revision_after"]["amendment_law_title"] == "改正法"
    assert [d["article_num"] for d in doc["diffs"]] == ["1"]
    assert doc["stats"]["modified"] == 1
    assert "pending" not in doc

def test_build_diff_document_refuses_an_unlisted_revision():
    before = _law([_article("1", "旧")], "X_20260331")
    after = _law([_article("1", "新")], "X_20260401")
    import pytest
    with pytest.raises(ValueError, match="does not list"):
        diff.build_diff_document("X", "2026-03-31", "2026-04-01", before, after, [])
```
（`_law` の木の形が `find_articles` に合わない場合は `tests/test_diff_suppl.py` のフィクスチャの形に合わせる。）

- [ ] **Step 3: `uv run pytest tests/test_diff_document.py -v` → `AttributeError: build_diff_document`**

- [ ] **Step 4: 実装** — `main()` の「Extract articles」から `output` 組み立てまでを関数へ移す。`main()` はファイル読込・`tables_changed`・空判定・`_revisions.json` 読込・書き出しを残し、間を `build_diff_document` 呼び出しに置き換える。`compute_diff` の ValueError は `main` で今と同じ文言で捕まえる。「revision が一覧に無い」は関数が `ValueError(f"{rev_path_hint} does not list revision {own_id!r}")` を投げ、`main` が今と同じ `Error: ... Re-run fetch.py.` を出して exit 1。

```python
def build_diff_document(law_id, date_before, date_after, before_data, after_data, revisions):
    law_title = before_data["revision_info"]["law_title"]
    before_revision = before_data["revision_info"]
    after_revision = after_data["revision_info"]
    diffs = compute_diff(find_articles(before_data["law_full_text"]),
                         find_articles(after_data["law_full_text"]))
    own_id = after_revision.get("law_revision_id")
    if not own_id or not any(r.get("law_revision_id") == own_id for r in revisions):
        raise ValueError(f"the revision list does not list revision {own_id!r}")
    titles = amendment_titles_on(revisions, date_after,
                                 after_revision.get("amendment_law_title") or "", own_id)
    for d in diffs:  # section paths — moved verbatim from main()
        ...
    stats = compute_stats(diffs)
    output = {...}  # moved verbatim, key order unchanged
    if len(titles) > 1:
        output["revision_after"]["amendment_law_titles"] = titles
    return output
```
順序の注意: 今の `main` は「表の変化」「差分ゼロ」を revision 検査より**先に**判定している。`main` では `compute_diff` だけ先に呼ぶ形を保つため、`main` は `find_articles`/`compute_diff` → 表 → 空 → `build_diff_document`（中で compute_diff を再計算してよい。純関数で決定的）の順にする。

- [ ] **Step 5: 出力不変を確かめる** — `OUT=after` で Step 1 のブロックを回し、`diff -r $TMPDIR/pending-baseline $TMPDIR/pending-after` が無出力（JSON・標準出力・`rc.txt` すべて一致）。ブロック末尾で `data/diffs` は毎回バックアップから戻る。
- [ ] **Step 6: `uv run pytest` 全緑 → commit `refactor: diff.py の文書組み立てを build_diff_document に切り出す`**

### Task 2: `scripts/pending.py`（AI を通らない出荷と `--check`）

**Files:**
- Create: `scripts/pending.py`
- Test: `tests/test_pending.py`

**Interfaces:**
- Consumes: `diff.build_diff_document`, `diff.tables_changed`, `diff.find_articles`, `diff.compute_diff`, `fetch.fetch_law_data`, `fetch.fetch_law_revisions`
- Produces（純関数、テスト対象）:
  - `today_jst() -> str`
  - `pending_dates(revisions: list[dict], today: str) -> dict[str, list[dict]]` — `current_revision_status == "UnEnforced"` かつ `amendment_enforcement_date > today` を施行日ごとに束ねる（日付昇順）。`amendment_enforcement_date` が None の UnEnforced は `ValueError`（日付不明を黙って落とさない）。
  - `basis_ids(revisions: list[dict], date: str) -> list[str]` — **状態を問わず**施行日 ≤ `date` の revision id を昇順で（施行前 diff の前後の版を決める集合。施行済みへの切替で誤報せず、合間に成立・施行された改正を拾う）。日付の無い revision は `"<id>@?"` として含める。
  - `pending_block(revs: list[dict], generated_on: str, basis: list[str]) -> dict` → `{"generated_on": ..., "basis_revision_ids": basis, "revisions": [{"law_revision_id","amendment_law_title","amendment_law_num","enforcement_comment","scheduled_enforcement_date"}]}`（`enforcement_comment` は空文字なら None）
  - `check_shipped(shipped: list[dict], revisions_by_law: dict[str, list[dict]], today: str) -> list[str]` — 問題の文のリスト（空なら健全）。例外を投げない（日付の無い UnEnforced も文として報告）。
- Produces（JSON）: 施行前 diff はトップレベルに `"pending": pending_block(...)` を持つ。それ以外は `build_diff_document` の出力そのまま。

CLI: `pending.py <law_id> | --all` で生成・出荷、`--check` を付けると取得して検査のみ（書かない）。`--all` は `frontend/public/data/timelines/*.json` の law_id 全部。終了コード: 生成時は「どれかの法令でエラー」なら 1。表変更の保留・空は、**その組が未出荷なら** 0 で報告のみ、**出荷済みなら** エラー（`diff.py:540` と同じ: 古いページが出続けるのを人が決める）。`--check` は問題 1 件以上で 1。判定順は `diff.main` と同じ **表 → 空**（表だけの改正は `compute_diff` が空になるため）。

- [ ] **Step 1: 失敗するテスト**

```python
# tests/test_pending.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import pending
import pytest

def _rev(rid, date, status="UnEnforced", comment="", sched=None, num="令和五年法律第五十三号", title="整備法"):
    return {"law_revision_id": rid, "amendment_enforcement_date": date,
            "current_revision_status": status, "amendment_enforcement_comment": comment,
            "amendment_scheduled_enforcement_date": sched, "amendment_law_num": num,
            "amendment_law_title": title}

def test_pending_dates_keeps_only_future_unenforced():
    revs = [_rev("a", "2028-06-13"), _rev("b", "2026-04-01", status="CurrentEnforced"),
            _rev("c", "2026-10-11")]  # today itself is in force, not pending
    assert list(pending.pending_dates(revs, "2026-10-11")) == ["2028-06-13"]

def test_same_day_pending_revisions_are_all_listed():
    revs = [_rev("a", "2028-12-23", title="甲法"), _rev("b", "2028-12-23", title="乙法")]
    assert [r["law_revision_id"] for r in pending.pending_dates(revs, "2026-10-11")["2028-12-23"]] == ["a", "b"]

def test_unenforced_without_a_date_stops():
    with pytest.raises(ValueError):
        pending.pending_dates([_rev("a", None)], "2026-10-11")

def test_pending_block_keeps_the_comment_verbatim_and_blank_as_none():
    c = "公布の日から起算して五年を超えない範囲内において政令で定める日"
    b = pending.pending_block([_rev("a", "2028-06-13", comment=c, sched="2028-06-13"),
                               _rev("b", "2028-06-13", comment="")], "2026-10-11", ["a", "b"])
    assert b["basis_revision_ids"] == ["a", "b"]
    assert b["revisions"][0]["enforcement_comment"] == c
    assert b["revisions"][0]["scheduled_enforcement_date"] == "2028-06-13"
    assert b["revisions"][1]["enforcement_comment"] is None
    assert b["generated_on"] == "2026-10-11"

def _shipped(date_after, rids, basis=None):
    return {"_diff_id": f"L_x_{date_after}", "law_id": "L", "date_after": date_after,
            "pending": {"generated_on": "2026-10-11", "basis_revision_ids": basis or rids,
                        "revisions": [{"law_revision_id": r} for r in rids]}}

def test_basis_ids_are_every_unenforced_up_to_the_date():
    revs = [_rev("a", "2027-06-23"), _rev("b", "2028-06-13"), _rev("c", "2029-01-01"),
            _rev("d", "2026-04-01", status="CurrentEnforced")]
    assert pending.basis_ids(revs, "2028-06-13") == ["a", "b", "d"]

def test_an_earlier_revision_taking_effect_is_not_a_change():
    shipped = _shipped("2028-06-13", ["b"], basis=["a", "b"])
    revs = [_rev("a", "2027-06-23", status="CurrentEnforced"), _rev("b", "2028-06-13")]
    assert pending.check_shipped([shipped], {"L": revs}, "2027-07-01") == []

def test_a_law_enacted_and_enforced_between_checks_is_caught():
    shipped = _shipped("2028-06-13", ["b"], basis=["b"])
    revs = [_rev("n", "2026-12-01", status="CurrentEnforced"), _rev("b", "2028-06-13")]
    assert pending.check_shipped([shipped], {"L": revs}, "2027-01-01")

def test_check_reports_a_comment_that_was_settled():
    shipped = _shipped("2028-06-13", ["a"])
    shipped["pending"]["revisions"][0].update(enforcement_comment="政令で定める日", scheduled_enforcement_date="2028-06-13")
    assert pending.check_shipped([shipped], {"L": [_rev("a", "2028-06-13")]}, "2026-10-11")

def test_check_reports_a_changed_basis():
    # a earlier pending law moved past D: D's before-text changed though D itself did not
    probs = pending.check_shipped([_shipped("2028-06-13", ["b"], basis=["a", "b"])],
                                  {"L": [_rev("a", "2029-01-01"), _rev("b", "2028-06-13")]}, "2026-10-11")
    assert probs and "前後の版" in probs[0]

def test_check_reports_an_undated_revision_without_raising():
    probs = pending.check_shipped([_shipped("2028-06-13", ["a"])],
                                  {"L": [_rev("a", "2028-06-13"), _rev("x", None)]}, "2026-10-11")
    assert any("x" in p for p in probs)

def test_check_passes_when_still_pending():
    assert pending.check_shipped([_shipped("2028-06-13", ["a"])],
                                 {"L": [_rev("a", "2028-06-13")]}, "2026-10-11") == []

def test_check_reports_enforced():
    probs = pending.check_shipped([_shipped("2028-06-13", ["a"])],
                                  {"L": [_rev("a", "2028-06-13", status="CurrentEnforced")]}, "2028-06-14")
    assert probs and "施行" in probs[0]

def test_check_reports_moved_date():
    probs = pending.check_shipped([_shipped("2028-06-13", ["a"])],
                                  {"L": [_rev("a", "2027-10-01")]}, "2026-10-11")
    assert probs and "日付" in probs[0]

def test_check_reports_a_new_same_day_revision():
    probs = pending.check_shipped([_shipped("2028-06-13", ["a"])],
                                  {"L": [_rev("a", "2028-06-13"), _rev("z", "2028-06-13")]}, "2026-10-11")
    assert probs and "z" in probs[0]

def test_check_reports_a_vanished_revision():
    probs = pending.check_shipped([_shipped("2028-06-13", ["a"])], {"L": []}, "2026-10-11")
    assert probs
```
加えて `test_a_shipped_pair_that_became_empty_is_an_error`（`shipped_ids` 引数にその組の id を渡した状態で空の組 → `errors` に入る）と `test_tables_changed_is_withheld_and_run_continues`: `process_law(law_id, revisions, fetch_data, today, shipped_ids=frozenset())` の `fetch_data` をフェイクにし、1 日目は表変更、2 日目は通常の木を返す。戻り値の `published == [2日目のid]`・`withheld == [1日目のid]`・`errors == []`。ファイルは一切書かれない（tmp_path も不要）。加えて `test_a_wrong_before_revision_is_an_error`（before の revision id が直前の施行待ちでない → errors）。

- [ ] **Step 2: `uv run pytest tests/test_pending.py -v` → ModuleNotFoundError**

- [ ] **Step 3: 実装**

```python
"""Publish not-yet-enforced amendments as diffs, with no AI prose.

Usage:
    python scripts/pending.py <law_id> | --all [--check]

Whether a revision is pending, and its date, come from a law_revisions list
fetched in this run — never from data/raw, whose age nothing records (the
same reason law_summary.py fetches its own evidence). --check only reads:
it reports shipped pending diffs that were enforced, moved or changed, and
exits 1; deleting or regenerating them is a human call.
"""
import datetime, json, sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import diff
import fetch

JST = ZoneInfo("Asia/Tokyo")
ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIRS = (ROOT / "data" / "diffs", ROOT / "frontend" / "public" / "data")
TIMELINE_DIR = ROOT / "frontend" / "public" / "data" / "timelines"

def today_jst() -> str:
    return datetime.datetime.now(JST).date().isoformat()

def pending_dates(revisions, today):
    out: dict[str, list[dict]] = {}
    for r in revisions:
        if r.get("current_revision_status") != "UnEnforced":
            continue
        date = r.get("amendment_enforcement_date")
        if not date:
            raise ValueError(f"UnEnforced revision without a date: {r.get('law_revision_id')}")
        if date > today:
            out.setdefault(date, []).append(r)
    return dict(sorted(out.items()))

def basis_ids(revisions, date):
    ids = []
    for r in revisions:
        d = r.get("amendment_enforcement_date")
        if d is None:
            ids.append(f"{r.get('law_revision_id')}@?")
        elif d <= date:
            ids.append(r["law_revision_id"])
    return sorted(ids)

def pending_block(revs, generated_on, basis):
    return {"generated_on": generated_on, "basis_revision_ids": basis, "revisions": [{
        "law_revision_id": r["law_revision_id"],
        "amendment_law_title": r.get("amendment_law_title"),
        "amendment_law_num": r.get("amendment_law_num"),
        "enforcement_comment": r.get("amendment_enforcement_comment") or None,
        "scheduled_enforcement_date": r.get("amendment_scheduled_enforcement_date"),
    } for r in revs]}

def check_shipped(shipped, revisions_by_law, today):
    problems = []
    for doc in shipped:
        did, revs = doc["_diff_id"], revisions_by_law.get(doc["law_id"], [])
        by_id = {r["law_revision_id"]: r for r in revs}
        if doc["date_after"] <= today:
            problems.append(f"{did}: 施行日を過ぎた — 通常のパイプラインで作り直す")
            continue
        for p in doc["pending"]["revisions"]:
            r = by_id.get(p["law_revision_id"])
            if r is None:
                problems.append(f"{did}: {p['law_revision_id']} が改正一覧から消えた")
            elif r.get("current_revision_status") != "UnEnforced":
                problems.append(f"{did}: {p['law_revision_id']} は施行済みになった")
            elif r.get("amendment_enforcement_date") != doc["date_after"]:
                problems.append(f"{did}: {p['law_revision_id']} の施行日付が {r.get('amendment_enforcement_date')} に変わった")
            elif ((r.get("amendment_enforcement_comment") or None) != p.get("enforcement_comment")
                  or r.get("amendment_scheduled_enforcement_date") != p.get("scheduled_enforcement_date")):
                problems.append(f"{did}: {p['law_revision_id']} の施行日の確定状況（コメント・予定日）が変わった")
        listed = {p["law_revision_id"] for p in doc["pending"]["revisions"]}
        for r in revs:
            if (r.get("current_revision_status") == "UnEnforced"
                    and r.get("amendment_enforcement_date") == doc["date_after"]
                    and r["law_revision_id"] not in listed):
                problems.append(f"{did}: 同じ日に施行予定の {r['law_revision_id']} が載っていない")
        now = basis_ids(revs, doc["date_after"])
        if now != doc["pending"]["basis_revision_ids"]:
            problems.append(f"{did}: 前後の版の元になる施行待ちの集合が変わった {doc['pending']['basis_revision_ids']} -> {now}")
    return problems
```
`process_law(law_id, revisions, fetch_data, today, out_dirs=OUT_DIRS)`: `pending_dates` の各日付について before=`date-1日`, after=`date` を `fetch_data(law_id, asof)` で取り（`data/raw/<law>_<asof>.json` にも書く）、after の `revision_info.law_revision_id` がその日の revision のどれかであることを確かめる（違えば errors）。`tables_changed` なら withheld、次に `compute_diff` が空なら skip（どちらも出荷済みファイルがあれば errors）、それ以外は `doc = diff.build_diff_document(...)`; `doc["pending"] = pending_block(revs, today, basis_ids(revisions, date))`; before の `revision_info.law_revision_id` も検証する: 施行日 < D の revision のうち最も新しい日付のもの（同日複数ならそのどれか）でなければ errors（e-Gov が別の版を返すと複数の改正が混ざる）。`process_law` は**書かずに** `{"docs": {diff_id: doc}, "raws": {path_name: data}, "published", "withheld", "errors"}` を返す純粋寄りの関数にし、`raw_dir`/`out_dirs` を持たない。**書き出しと JST 日付の再確認は `main()`**: 全法令を処理し終えて JST の日付が `today` のままなら raw と diff を書く（変わっていたら何も書かず exit 1 — law_summary.py / articles.py と同じ）。中身（`generated_on` を除く）が出荷済みと同じなら書き直さない（enrich が足した `proposer` を消さない）。`--check` の main はファイル名の stem を `doc["_diff_id"]` に入れてから `check_shipped` に渡す。`today_jst()` は `pending.py` に置き、`annotate.py`/`explainer.py` は `from pending import today_jst`。`main()` は法令ごとに `fetch.fetch_law_revisions(law_id)` を取り、dict のまま `RAW_DIR/<law>_revisions.json` に書いてから `process_law(law_id, data["revisions"], ...)`。`--check` は `frontend/public/data/*_*_*.json` のうち `pending` を持つものを集め `check_shipped`。

- [ ] **Step 4: `uv run pytest tests/test_pending.py -v` 全緑**
- [ ] **Step 5: commit `feat: 施行予定の改正を AI なしで差分として出荷する pending.py`**

### Task 3: AI 経路から施行前を締め出す（annotate / explainer）＋出荷データのテスト

**Files:**
- Modify: `scripts/annotate.py:383` (`main` 冒頭), `scripts/explainer.py:24-61,282`
- Modify: `scripts/timeline.py`（entry に `enforcement_comment` を足す）
- Test: `tests/test_explainer.py`, `tests/test_shipped_data.py`, `tests/test_timeline.py`

**Interfaces:**
- `select_changes(timeline: list[dict], today: str, pending_ids: frozenset[str] = frozenset()) -> list[dict]` — **ループの冒頭（`by_title` に入れる前）**で、施行前の entry（`enforcement_date > today`、`enforcement_comment` あり、または `diff_id in pending_ids`）の `diff_id` を None にする。`main()` は出荷済み diff のうち `pending` を持つものの stem を `pending_ids` に渡す（日付を過ぎた固定日の施行前 diff が同名の施行済み entry に勝つのを防ぐ — Gate2 第2周 #3）。こうしないと同名タイトルの重複除去（`explainer.py:44-48`）が施行前の diff を勝たせ、施行済みで根拠のある entry が消える（Gate2 で民法の年表で実測）。
- `articles.collect_changes`: `if doc["date_after"] > today or "pending" in doc: continue`。
- `annotate.refuses_pending(data: dict, today: str) -> str | None` — `"pending" in data or data["date_after"] > today` なら理由文。
- timeline entry: `"enforcement_comment": rev.get("amendment_enforcement_comment") or None` を**値があるときだけ**足す（既存 entry のバイトを変えない）。

- [ ] **Step 1: 失敗するテスト**

```python
# tests/test_explainer.py に追加
def test_a_pending_diff_never_grounds_an_explainer_entry():
    timeline = [{"amendment_law_title": "整備法", "enforcement_date": "2028-06-13",
                 "diff_id": "L_2028-06-12_2028-06-13"}]
    [c] = select_changes(timeline, "2026-10-11")
    assert c["grounded"] is False and c["diff_id"] is None

def test_same_title_keeps_the_enforced_grounded_entry():
    timeline = [
        {"amendment_law_title": "民法等の一部を改正する法律", "enforcement_date": "2029-06-23",
         "diff_id": "L_2029-06-22_2029-06-23", "enforcement_comment": "政令で定める日"},
        {"amendment_law_title": "民法等の一部を改正する法律", "enforcement_date": "2026-06-24",
         "diff_id": "L_2026-06-23_2026-06-24"},
    ]
    [c] = select_changes(timeline, "2026-10-11")
    assert c["grounded"] is True and c["enforcement_date"] == "2026-06-24"

def test_an_overdue_pending_diff_does_not_beat_the_enforced_one():
    timeline = [
        {"amendment_law_title": "整備法", "enforcement_date": "2026-11-02", "diff_id": "L_2026-11-01_2026-11-02"},
        {"amendment_law_title": "整備法", "enforcement_date": "2026-07-17", "diff_id": "L_2026-07-16_2026-07-17"},
    ]
    [c] = select_changes(timeline, "2026-12-01", frozenset({"L_2026-11-01_2026-11-02"}))
    assert c["grounded"] is True and c["enforcement_date"] == "2026-07-17"

def test_a_commented_entry_stays_pending_after_its_date():
    timeline = [{"amendment_law_title": "整備法", "enforcement_date": "2026-11-26",
                 "diff_id": "L_2026-11-25_2026-11-26", "enforcement_comment": "政令で定める日"}]
    [c] = select_changes(timeline, "2026-12-01")
    assert c["grounded"] is False
```

```python
# tests/test_articles.py に追加（既存の _doc ヘルパの形に合わせる）
def test_collect_changes_skips_pending_docs():
    doc = _doc("2026-04-01", [...])  # 既存テストの 1 entry をそのまま流用
    doc["pending"] = {"generated_on": "2026-03-01", "basis_revision_ids": [], "revisions": []}
    assert articles.collect_changes([doc], "2026-10-11") == {}
```
既存の `select_changes(timeline)` 呼び出し 5 箇所は `select_changes(timeline, "2099-12-31")`（全部施行済み扱い＝従来どおり）に書き換える。

```python
# tests/test_annotate_validation.py に追加
from annotate import refuses_pending
def test_annotate_refuses_pending_diffs():
    assert refuses_pending({"date_after": "2028-06-13"}, "2026-10-11")
    assert refuses_pending({"date_after": "2026-04-01", "pending": {}}, "2026-10-11")
    assert refuses_pending({"date_after": "2026-04-01"}, "2026-10-11") is None
```

```python
# tests/test_shipped_data.py に追加（時計に依存しない）
def _pending_diffs():
    return [(p, json.loads(p.read_text())) for p in shipped_diffs()
            if "pending" in json.loads(p.read_text())]

def test_pending_diffs_carry_no_ai_prose():
    for p, d in _pending_diffs():
        assert "pr_summary" not in d, p.name
        assert not any("annotation" in e for e in d["diffs"]), p.name

def test_pending_diffs_agree_with_their_timeline():
    for p, d in _pending_diffs():
        tl = json.loads((SHIPPED / "timelines" / f"{d['law_id']}.json").read_text())
        by_id = {e["law_revision_id"]: e for e in tl["timeline"]}
        for r in d["pending"]["revisions"]:
            e = by_id.get(r["law_revision_id"])
            assert e and e["enforcement_date"] == d["date_after"], (p.name, r["law_revision_id"])
            assert e["diff_id"] == p.stem, p.name

```
（explainer 側の出荷データテストは置かない: `normalize_explainer` は `diff_id` を捨てるので
出荷物から施行前 diff への紐付けを引けず、空振りするテストになる — Gate2 #6。防御は
`select_changes` の単体テストと `apply_diff` の pr_summary 無し→ungrounded の 2 段。）

- [ ] **Step 2: 赤を確認** → **Step 3: 実装**（`annotate.main` は `data = json.loads(...)` の直後・`anthropic.Anthropic()` の前に `refuses_pending(data, today_jst())` が真なら `ERROR: ... pending diffs carry no AI prose (spec docs/pending-amendments)` で exit 1。`explainer.main` は `select_changes(timeline["timeline"], today_jst())`。`timeline.py` は entry 組み立てに comment を条件付きで追加）→ **Step 4: `uv run pytest` 全緑** → **Step 5: commit `feat: 施行前の差分を AI 生成の根拠から締め出す`**

### Task 4: データ生成

- [ ] 順序厳守: `pending.py --all` → `timeline.py`（全法令）→ `enrich.py`。enrich を飛ばすと `test_a_diffs_proposer_is_its_timeline_entrys` が赤になる。
- [ ] `uv run python scripts/pending.py --all` — 公開数・保留（表）・空を記録
- [ ] `for id in $(ls frontend/public/data/timelines | sed 's/.json//'); do uv run python scripts/timeline.py $id; done`（中身を取り直した `_revisions.json` で年表を再構築。carry_over で解説等は保持）
- [ ] `uv run python scripts/enrich.py`（年表の提案者を施行前 diff にも写す。同日複数は付けない既存規則）
- [ ] `uv run python scripts/pending.py --all --check` → exit 0、`uv run pytest` 全緑
- [ ] `git diff --stat` で施行済み diff・既存 entry に変化が無いことを確認（`timelines/*.json` の差分は新 entry の `diff_id`/`enforcement_comment` と、取り直しで変わった一覧だけ）
- [ ] commit `data: 施行予定の改正 N 件の差分を追加`

### Task 5: フロント — 判定の 1 か所と各表示

**Files:**
- Create: `frontend/lib/pending.ts`
- Modify: `frontend/lib/types.ts`, `frontend/app/diff/[diffId]/page.tsx`, `frontend/components/revision-header.tsx`, `frontend/components/timeline.tsx`, `frontend/app/page.tsx`, `frontend/app/sitemap.ts`

**Interfaces:**
```ts
// lib/types.ts
export interface PendingRevision {
  law_revision_id: string; amendment_law_title: string | null; amendment_law_num: string | null;
  enforcement_comment: string | null; scheduled_enforcement_date: string | null;
}
export interface PendingInfo { generated_on: string; revisions: PendingRevision[] }
// LawDiffData に: pending?: PendingInfo;   TimelineEntry に: enforcement_comment?: string | null;

// lib/pending.ts
/** JST calendar date at build time; SSG pages are frozen at this date. */
export const BUILD_DATE_JST: string = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
export function isPendingDate(date: string): boolean { return date > BUILD_DATE_JST; }
/** Fail closed: a diff built as pending stays pending until the pipeline
 *  rebuilds it — its date may be a 政令 deadline, not the day it took effect. */
export function isPendingDiff(d: LawDiffData): d is LawDiffData & { pending: PendingInfo } {
  return !!d.pending;
}
/** Past its date but never rebuilt: we no longer know whether it took effect. */
export function isOverduePending(d: LawDiffData & { pending: PendingInfo }): boolean {
  return !isPendingDate(d.date_after);
}
/** Timeline entries: pending when it links to a pending diff (same ground as
 *  the diff page), carries a 施行日 comment (only unenforced revisions do), or
 *  is dated after the build. `pendingDiffIds` comes from getDiffIds(). */
export function isPendingEntry(e: TimelineEntry, pendingDiffIds: ReadonlySet<string>): boolean {
  return (!!e.diff_id && pendingDiffIds.has(e.diff_id)) || !!e.enforcement_comment || isPendingDate(e.enforcement_date);
}
/** Every claim on a pending page is dated: true now, still true after the date. */
export function asOfLabel(d: LawDiffData & { pending: PendingInfo }): string {
  return `${d.pending.generated_on}時点で未施行`;
}
/** Name for a pending diff: the amending laws' numbers — facts, unlike a year. */
export function pendingName(d: LawDiffData & { pending: PendingInfo }): string {
  return d.pending.revisions.map((r) => r.amendment_law_num || r.amendment_law_title || r.law_revision_id).join("／");
}
```

- [ ] **diff ページ** `generateMetadata`: `year` は施行済みの分岐の中でだけ計算する。`isPendingDiff(data)` なら title・`openGraph.title`・`openGraph.description` をすべて施行前用に組む。title=`${law_title}【${asOfLabel}】${pendingName}による改正`、description=`${law_title}の改正（${pendingName}。${asOfLabel}）による新旧条文の差分。施行日: ${施行日表示}。施行されると本則${mainCount}条が変わります。` 附則のみは `施行されると附則${supplCount}件が変わります（本則は変わりません）。`。施行日表示は revision ごとに `enforcement_comment ?? date_after`（段階施行の同じ改正法番号のページを説明文で区別する — 第2周 #9）。
- [ ] **パンくず JSON-LD**（`page.tsx:75`）: 施行前は `pendingName(data)`。**DiffStats**（`diff-stats.tsx:79`）: 施行前は「施行されると本則 N 条が変わります」。
- [ ] **RevisionHeader**: 施行前なら見出し下に帯「施行前 — このページの作成時点（{generated_on}）では、まだ施行されていません。」（`isOverduePending` なら「{generated_on} 時点の施行予定の情報です。施行されたか・内容が変わったかは未確認です。」）と、revision ごとに `enforcement_comment ? 「施行日: {comment}（e-Gov 上の予定日: {scheduled}）」 : 「施行日: {date_after}」`。日付チップは、施行前なら「改正直前 → 施行後（e-Gov 上の予定日 {date_after}）」とし、未確定日から 1 日引いただけの `date_before` は出さない。
- [ ] **Timeline**: `isPendingEntry(entry, pendingDiffIds)`（`Timeline` に `pendingDiffIds` を props で渡す）なら日付の前に「施行予定」チップ、`enforcement_comment` があれば日付の代わりに「{comment}（e-Gov 上の予定日 {date}）」を小さく。
- [ ] **テーマページ**（`theme/[themeId]/page.tsx:89,127`）: 「最新の差分」は `isPendingEntry(e, pendingDiffIds)` でない entry の diff から拾う。`差分あり` は施行前なら `差分あり（施行前）`。
- [ ] **トップ**: `diffs` を `isPendingDiff` で 2 つに分け、「最新」一覧と目玉は施行前でないものだけから。「施行予定の改正」節は施行前のうち `!isOverduePending` のものだけを、見出しに `asOfLabel` の日付を添えて `law_title`・`pendingName`・施行日表示（上と同じ規則）でリンクを並べる（最大 5 件、施行日昇順）。
- [ ] **sitemap**: diff の `lastModified` は施行前なら `data.pending.generated_on`。`latestDiffDate` は施行済みの diff だけから。法令ページは `timeline.find((e) => !isPendingEntry(e, pendingDiffIds))?.enforcement_date`。
- [ ] `cd frontend && npm run lint && npm run build` 緑。`npm run dev -- -p 3002` で `/diff/129AC0000000089_2028-06-12_2028-06-13`・`/`・`/law/129AC0000000089` を目視（スクリーンショット）。
- [ ] commit `feat: 施行予定の差分ページと年表・トップ・サイトマップの施行前表示`

### Task 6: 文書

- [ ] `CLAUDE.md` の Development Commands に `uv run python scripts/pending.py --all [--check]`、AI-Generated Content 節に 1 段落（施行前 diff は AI を通らない・`refuses_pending`・explainer の grounded 条件・`--check` は鮮度の唯一の検査）。README のパイプライン手順に 8 として追記。
- [ ] commit `docs: 施行予定の差分の生成手順と規則を記す`
