# `/law`「最近の改正をわかりやすく」解説 実装プラン（B案 Phase1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/law/{lawId}` ページに、最近の改正を平易に解説するAI生成セクションを追加し、検索露出をクリックに変える（Phase1=4法令）。

**Architecture:** 既存 `law_summary.py` と同じ疎結合パターン。新規 `scripts/explainer.py` がClaudeで `explainer` を生成しtimeline JSONに格納。Pythonの選別/正規化/検証は純関数化してTDD。フロントは `LawExplainerSection` コンポーネントで描画。`explainer?` はoptionalで後方互換。

**Tech Stack:** Python 3.13 (uv, anthropic), pytest, Next.js App Router, TypeScript, Tailwind。

設計spec: `docs/superpowers/specs/2026-06-09-law-explainer-seo-design.md`

---

## File Structure

- `frontend/lib/types.ts`（変更）— `ExplainerChange`/`ExplainerFaq`/`LawExplainer` 追加、`LawTimeline.explainer?`。
- `scripts/explainer.py`（新規）— 選別`select_changes`・正規化`normalize_explainer`・検証`validate_explainer`の純関数＋Claude生成＋I/O。
- `tests/test_explainer.py`（新規）— 純関数のpytest。
- `frontend/components/law-explainer.tsx`（新規）— 描画コンポーネント。
- `frontend/app/law/[lawId]/page.tsx`（変更）— セクション描画＋`generateMetadata`のdescription優先順位。
- データ: `data/timelines/{4法令}.json` と `frontend/public/data/timelines/{4法令}.json`（生成物）。

Phase1対象 law_id: `416AC0000000123`(不動産登記法) / `129AC0000000089`(民法) / `322AC0000000049`(労働基準法) / `335AC0000000105`(道路交通法)。

---

## Task 1: 型定義の追加

**Files:**
- Modify: `frontend/lib/types.ts`（`LawTimeline` interface 付近、現状106-116行）

- [ ] **Step 1: 型を追加**

`frontend/lib/types.ts` の `LawSummary` interface（93-97行）の直後に追加：

```ts
export interface ExplainerChange {
  year: string;
  title: string;
  what: string;
  why?: string;
  impact?: string;
  grounded: boolean;
}

export interface ExplainerFaq {
  q: string;
  a: string;
}

export interface LawExplainer {
  intro: string;
  recent_changes: ExplainerChange[];
  faq: ExplainerFaq[];
}
```

`LawTimeline` interface に1行追加：

```ts
export interface LawTimeline {
  law_id: string;
  law_title: string;
  law_num: string;
  promulgation_date: string;
  revision_count: number;
  timeline: TimelineEntry[];
  summary?: LawSummary;
  category?: string;
  contributors?: Contributor[];
  explainer?: LawExplainer;
}
```

- [ ] **Step 2: 型チェック**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS（エラーなし。`explainer`はoptionalなので既存コード影響なし）

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat: add LawExplainer types"
```

---

## Task 2: pytest 導入と選別関数 `select_changes`（TDD）

**Files:**
- Modify: `pyproject.toml`（dev依存）
- Create: `scripts/explainer.py`
- Create: `tests/test_explainer.py`

- [ ] **Step 1: pytest を dev 依存に追加**

Run: `uv add --dev pytest`
Expected: `pyproject.toml` に `[dependency-groups]` または `[tool.uv]` でpytestが追加され、`uv.lock`更新。

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_explainer.py` を作成：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from explainer import select_changes


def test_select_dedupes_by_title_prefers_diff_id():
    timeline = [
        {"enforcement_date": "2024-04-01", "amendment_law_title": "民法等の一部を改正する法律",
         "diff_id": "129_2024"},
        {"enforcement_date": "2026-04-01", "amendment_law_title": "民法等の一部を改正する法律",
         "diff_id": None},
    ]
    result = select_changes(timeline)
    # same title collapses to one, the diff_id-bearing entry wins (grounded)
    assert len(result) == 1
    assert result[0]["grounded"] is True
    assert result[0]["diff_id"] == "129_2024"
    assert result[0]["year"] == "2024"


def test_select_grounded_first_then_date_desc():
    timeline = [
        {"enforcement_date": "2020-01-01", "amendment_law_title": "A法", "diff_id": "d1"},
        {"enforcement_date": "2025-01-01", "amendment_law_title": "B法", "diff_id": None},
        {"enforcement_date": "2023-01-01", "amendment_law_title": "C法", "diff_id": None},
    ]
    result = select_changes(timeline)
    # grounded (A) first, then ungrounded by date desc (B 2025, C 2023)
    assert [c["year"] for c in result] == ["2020", "2025", "2023"]
    assert result[0]["grounded"] is True
    assert result[1]["grounded"] is False


def test_select_caps_at_four_and_skips_empty_title():
    timeline = [{"enforcement_date": f"20{10+i}-01-01",
                 "amendment_law_title": f"法{i}", "diff_id": None} for i in range(6)]
    timeline.append({"enforcement_date": "2030-01-01", "amendment_law_title": "", "diff_id": None})
    result = select_changes(timeline)
    assert len(result) == 4
    assert all(c["year"] for c in result)
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: FAIL（`ModuleNotFoundError` か `ImportError: cannot import name 'select_changes'`）

- [ ] **Step 4: `scripts/explainer.py` に最小実装**

`scripts/explainer.py` を作成（まず定数と `select_changes` のみ）：

```python
"""Generate a plain-language 'recent amendments' explainer for a law using Claude AI.

Usage:
    python scripts/explainer.py <law_id>

Example:
    python scripts/explainer.py 416AC0000000123
"""

import sys
import json
import os
from pathlib import Path

MODEL = "claude-sonnet-4-6"
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend" / "public" / "data"
MAX_CHANGES = 4


def select_changes(timeline: list[dict]) -> list[dict]:
    """Deterministically select up to MAX_CHANGES meaningful amendments.

    - dedupe by amendment_law_title (keep the diff_id-bearing entry, else latest date)
    - grounded = bool(diff_id)
    - order: grounded first, then enforcement_date descending
    """
    by_title: dict[str, dict] = {}
    for entry in timeline:
        title = entry.get("amendment_law_title", "")
        if not title:
            continue
        cand = {
            "source_title": title,
            "enforcement_date": entry.get("enforcement_date", "") or "",
            "diff_id": entry.get("diff_id"),
        }
        cur = by_title.get(title)
        if cur is None:
            by_title[title] = cand
            continue
        cur_has, cand_has = bool(cur["diff_id"]), bool(cand["diff_id"])
        if (cand_has and not cur_has) or (
            cand_has == cur_has and cand["enforcement_date"] > cur["enforcement_date"]
        ):
            by_title[title] = cand

    changes = [
        {
            "year": c["enforcement_date"][:4] if c["enforcement_date"] else "",
            "source_title": c["source_title"],
            "enforcement_date": c["enforcement_date"],
            "diff_id": c["diff_id"],
            "grounded": bool(c["diff_id"]),
        }
        for c in by_title.values()
    ]
    changes.sort(key=lambda c: (c["grounded"], c["enforcement_date"]), reverse=True)
    return changes[:MAX_CHANGES]
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: PASS（3 tests）

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock scripts/explainer.py tests/test_explainer.py
git commit -m "feat: add select_changes with pytest (explainer Phase1)"
```

---

## Task 3: 検証関数 `validate_explainer`（TDD）

**Files:**
- Modify: `scripts/explainer.py`
- Modify: `tests/test_explainer.py`

- [ ] **Step 1: 失敗するテストを追加**

`tests/test_explainer.py` の import 行に `validate_explainer` を追加し、末尾にテストを追加：

```python
from explainer import select_changes, validate_explainer

VALID_YEARS = {"2024", "2026"}


def _ok_explainer():
    return {
        "intro": "不動産登記法は近年、相続登記の義務化など大きな改正が続いています。マイホームや相続の手続きに直接関わる重要な変更です。",
        "recent_changes": [
            {"year": "2024", "title": "相続登記の義務化", "what": "相続を知った日から3年以内の登記が必須になりました。",
             "why": "所有者不明土地の増加が社会問題化したためです。", "impact": "相続人は期限内の手続きが必要です。", "grounded": True},
            {"year": "2026", "title": "登記手続のデジタル化", "what": "オンラインでの手続きが拡充されました。", "grounded": False},
        ],
        "faq": [{"q": "相続登記はいつから義務？", "a": "2024年4月1日から施行されています。"}],
    }


def test_validate_passes_on_good_explainer():
    assert validate_explainer(_ok_explainer(), VALID_YEARS) == []


def test_validate_flags_ungrounded_with_why():
    bad = _ok_explainer()
    bad["recent_changes"][1]["why"] = "推測の背景"
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("ungrounded" in e for e in errors)


def test_validate_flags_year_not_in_timeline():
    bad = _ok_explainer()
    bad["recent_changes"][0]["year"] = "1999"
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("year" in e for e in errors)


def test_validate_flags_missing_key():
    bad = _ok_explainer()
    del bad["intro"]
    errors = validate_explainer(bad, VALID_YEARS)
    assert any("intro" in e for e in errors)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: FAIL（`ImportError: cannot import name 'validate_explainer'`）

- [ ] **Step 3: `validate_explainer` を実装**

`scripts/explainer.py` の `select_changes` の下に追加：

```python
def validate_explainer(explainer: dict, valid_years: set[str]) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    errors: list[str] = []
    for key in ("intro", "recent_changes", "faq"):
        if key not in explainer:
            errors.append(f"missing key: {key}")
    if errors:
        return errors

    intro = explainer["intro"]
    if not isinstance(intro, str) or not (40 <= len(intro) <= 200):
        errors.append("intro length out of range (40-200)")

    rc = explainer["recent_changes"]
    if not isinstance(rc, list) or not (1 <= len(rc) <= MAX_CHANGES):
        errors.append(f"recent_changes count out of range (1-{MAX_CHANGES})")
    else:
        for i, c in enumerate(rc):
            for k in ("year", "title", "what", "grounded"):
                if k not in c:
                    errors.append(f"recent_changes[{i}] missing {k}")
            if c.get("year") not in valid_years:
                errors.append(f"recent_changes[{i}] year {c.get('year')} not in timeline")
            what = c.get("what", "")
            if not isinstance(what, str) or not (0 < len(what) <= 120):
                errors.append(f"recent_changes[{i}] what length out of range")
            if not c.get("grounded") and (c.get("why") or c.get("impact")):
                errors.append(f"recent_changes[{i}] ungrounded must not have why/impact")

    faq = explainer["faq"]
    if not isinstance(faq, list):
        errors.append("faq must be a list")
    else:
        for i, f in enumerate(faq):
            if not f.get("q") or not f.get("a"):
                errors.append(f"faq[{i}] missing q/a")
    return errors
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: PASS（7 tests）

- [ ] **Step 5: Commit**

```bash
git add scripts/explainer.py tests/test_explainer.py
git commit -m "feat: add validate_explainer (explainer Phase1)"
```

---

## Task 4: 正規化関数 `normalize_explainer`（TDD）

**Files:**
- Modify: `scripts/explainer.py`
- Modify: `tests/test_explainer.py`

LLM出力に決定的な `year`/`grounded` を再付与し、`faq`欠落→`[]`、ungroundedの`why`/`impact`除去を行う。

- [ ] **Step 1: 失敗するテストを追加**

import 行を `from explainer import select_changes, validate_explainer, normalize_explainer` に更新し、末尾に追加：

```python
def test_normalize_reattaches_year_grounded_and_strips_ungrounded():
    selected = [
        {"year": "2024", "source_title": "民法等の一部を改正する法律", "grounded": True},
        {"year": "2026", "source_title": "整理法", "grounded": False},
    ]
    raw = {
        "intro": "  導入文  ",
        "recent_changes": [
            {"title": "相続登記の義務化", "what": "3年以内に登記。", "why": "所有者不明土地対策。", "impact": "過料あり。"},
            {"title": "技術的整理", "what": "条ずれの整理。", "why": "LLMが勝手に書いた背景", "impact": "影響も勝手に"},
        ],
        # faq missing entirely
    }
    result = normalize_explainer(raw, selected)
    assert result["intro"] == "導入文"
    assert result["recent_changes"][0]["grounded"] is True
    assert result["recent_changes"][0]["why"] == "所有者不明土地対策。"
    # ungrounded: why/impact stripped
    assert result["recent_changes"][1]["grounded"] is False
    assert "why" not in result["recent_changes"][1]
    assert "impact" not in result["recent_changes"][1]
    # faq normalized to []
    assert result["faq"] == []


def test_normalize_filters_incomplete_faq():
    selected = [{"year": "2024", "source_title": "X", "grounded": True}]
    raw = {"intro": "x", "recent_changes": [{"title": "t", "what": "w", "why": "y", "impact": "i"}],
           "faq": [{"q": "問", "a": "答"}, {"q": "", "a": "答だけ"}, {"q": "問だけ"}]}
    result = normalize_explainer(raw, selected)
    assert result["faq"] == [{"q": "問", "a": "答"}]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: FAIL（`ImportError: cannot import name 'normalize_explainer'`）

- [ ] **Step 3: `normalize_explainer` を実装**

`scripts/explainer.py` の `validate_explainer` の下に追加：

```python
def normalize_explainer(raw: dict, selected: list[dict]) -> dict:
    """Re-attach deterministic year/grounded from `selected`, keep LLM prose,
    strip why/impact from ungrounded changes, normalize faq to a clean list."""
    changes = []
    for sel, item in zip(selected, raw.get("recent_changes", []) or []):
        change = {
            "year": sel["year"],
            "title": (item.get("title") or sel["source_title"]).strip(),
            "what": (item.get("what") or "").strip(),
            "grounded": sel["grounded"],
        }
        if sel["grounded"]:
            why = (item.get("why") or "").strip()
            impact = (item.get("impact") or "").strip()
            if why:
                change["why"] = why
            if impact:
                change["impact"] = impact
        changes.append(change)

    faq = [
        {"q": f.get("q", "").strip(), "a": f.get("a", "").strip()}
        for f in (raw.get("faq") or [])
        if f.get("q") and f.get("a")
    ]
    return {"intro": (raw.get("intro") or "").strip(), "recent_changes": changes, "faq": faq}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: PASS（9 tests）

- [ ] **Step 5: Commit**

```bash
git add scripts/explainer.py tests/test_explainer.py
git commit -m "feat: add normalize_explainer (explainer Phase1)"
```

---

## Task 5: 生成のグルー（Claude呼び出し＋I/O）

**Files:**
- Modify: `scripts/explainer.py`

純関数はテスト済み。ここでClaude呼び出し・pr_summary読み込み・プロンプト構築・main を足す。API依存のため自動テストは無し（Task7で実行検証）。

- [ ] **Step 1: import と補助I/Oを追加**

`scripts/explainer.py` の先頭 import 群に `import anthropic` を追加（`import os` の下）。

`normalize_explainer` の下に、`law_summary.py` と同じ `load_env` と pr_summary 読み込みを追加：

```python
def load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def load_pr_summary(diff_id: str) -> dict | None:
    """Load pr_summary for a diff_id from the frontend data dir or data/diffs."""
    for base in (FRONTEND_DIR, DATA_DIR / "diffs"):
        path = base / f"{diff_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return data.get("pr_summary")
    return None
```

- [ ] **Step 2: プロンプト構築と生成を追加**

```python
def build_prompt(law_title, law_num, category, summary_desc, changes):
    lines = []
    for i, c in enumerate(changes):
        block = [f"[改正{i + 1}] 施行年: {c['year']} / 改正法: {c['source_title']}"]
        if c["grounded"]:
            pr = c.get("pr_summary") or {}
            block.append("  根拠あり(grounded)。以下の差分要約に基づき、what/why/impactを書いてよい:")
            block.append(f"    タイトル: {pr.get('title', '')}")
            block.append(f"    概要: {pr.get('summary', '')}")
            block.append(f"    背景: {pr.get('background', '')}")
            block.append(f"    影響: {pr.get('impact', '')}")
        else:
            block.append("  根拠なし(ungrounded)。改正法名と施行年のみ確認済み。"
                         "whatは改正法名から言える範囲に留め、why/impactは書かないこと。")
        lines.append("\n".join(block))
    changes_text = "\n\n".join(lines)

    return f"""あなたは日本の法律をわかりやすく解説する専門家です。以下の法律の「最近の改正」を、一般市民向けにJSON形式で解説してください。

法令名: {law_title}
法令番号: {law_num}
分類: {category}
法律の概要: {summary_desc}

最近の主要改正（この{len(changes)}件についてのみ書く。順番・件数を変えない）:
{changes_text}

出力JSON形式:
{{
  "intro": "この法律で近年どんな改正が続いているかの導入（80-150字、専門用語を避ける）",
  "recent_changes": [
    {{"title": "改正の通称（例: 相続登記の義務化）", "what": "何が変わったか（40-100字）", "why": "なぜ変わったか（grounded時のみ・40-100字）", "impact": "私たちへの影響（grounded時のみ・40-100字）"}}
  ],
  "faq": [
    {{"q": "よくある質問（例: いつから？）", "a": "回答（40-120字）"}}
  ]
}}

ルール:
- recent_changes は入力の改正と同じ順番・同じ件数で出力する。
- ungrounded の改正では why/impact を出力しない（キーごと省略）。
- 提供情報に無い事実（数値・期限・因果）を断定しない。不確実なら書かない。
- 見出しや本文に「{law_title}」「改正」「わかりやすく」が自然に含まれるとよい。
- faq は0-3件。確実に答えられるものだけ。
- JSONのみを出力する。"""


def generate_explainer(law_title, law_num, category, summary_desc, changes) -> dict:
    client = anthropic.Anthropic()
    prompt = build_prompt(law_title, law_num, category, summary_desc, changes)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)
```

- [ ] **Step 3: main を追加**

```python
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    load_env()
    law_id = sys.argv[1]

    timeline_path = DATA_DIR / "timelines" / f"{law_id}.json"
    if not timeline_path.exists():
        print(f"Error: Run timeline.py first for {law_id}")
        sys.exit(1)
    timeline = json.loads(timeline_path.read_text())

    changes = select_changes(timeline["timeline"])
    if not changes:
        print(f"Error: no usable amendments for {law_id}")
        sys.exit(1)
    for c in changes:
        if c["grounded"] and c["diff_id"]:
            c["pr_summary"] = load_pr_summary(c["diff_id"])
            if not c["pr_summary"]:
                # diff file missing → downgrade to ungrounded for safety
                c["grounded"] = False

    print(f"Generating explainer for {timeline['law_title']} ({len(changes)} changes)...")
    raw = generate_explainer(
        timeline["law_title"],
        timeline["law_num"],
        timeline.get("category", ""),
        (timeline.get("summary") or {}).get("description", ""),
        changes,
    )
    explainer = normalize_explainer(raw, changes)

    valid_years = {e.get("enforcement_date", "")[:4] for e in timeline["timeline"]}
    errors = validate_explainer(explainer, valid_years)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        print("\nGenerated (not saved):")
        print(json.dumps(explainer, ensure_ascii=False, indent=2))
        sys.exit(2)

    timeline["explainer"] = explainer
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    frontend_path = FRONTEND_DIR / "timelines" / f"{law_id}.json"
    if frontend_path.exists():
        frontend_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))

    print(f"  intro: {explainer['intro'][:60]}...")
    print(f"  recent_changes: {len(explainer['recent_changes'])}, faq: {len(explainer['faq'])}")
    print(f"  Saved: {timeline_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: import が壊れていないことを確認（純関数テスト再実行）**

Run: `uv run pytest tests/test_explainer.py -v`
Expected: PASS（9 tests。`import anthropic` 追加後もテストは純関数のみ参照）

- [ ] **Step 5: Commit**

```bash
git add scripts/explainer.py
git commit -m "feat: add Claude generation + IO glue to explainer.py"
```

---

## Task 6: フロント描画コンポーネントとページ結線

**Files:**
- Create: `frontend/components/law-explainer.tsx`
- Modify: `frontend/app/law/[lawId]/page.tsx`

- [ ] **Step 1: コンポーネントを作成**

`frontend/components/law-explainer.tsx`：

```tsx
import { Icon } from "@/components/icon";
import type { LawExplainer } from "@/lib/types";

export function LawExplainerSection({
  lawTitle,
  explainer,
}: {
  lawTitle: string;
  explainer: LawExplainer;
}) {
  return (
    <section className="border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] flex items-center gap-2">
        <Icon name="history" size={16} className="opacity-40" />
        <h2 className="text-[15px] font-medium">
          {lawTitle}の最近の改正をわかりやすく
        </h2>
        <span className="text-[11px] opacity-40 ml-auto">AI要約</span>
      </div>
      <div className="px-4 py-4 space-y-5">
        <p className="text-[15px] leading-[26px]">{explainer.intro}</p>

        <div className="space-y-4">
          {explainer.recent_changes.map((c, i) => (
            <div
              key={i}
              className="border-t border-[var(--border)] pt-4 first:border-t-0 first:pt-0"
            >
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-mono text-[13px] text-[var(--diff-hunk-text)]">
                  {c.year}
                </span>
                <h3 className="text-[15px] font-bold">{c.title}</h3>
              </div>
              <dl className="space-y-1.5 text-[14px] leading-[24px]">
                <div>
                  <dt className="inline font-medium">何が変わった？ </dt>
                  <dd className="inline opacity-70">{c.what}</dd>
                </div>
                {c.why && (
                  <div>
                    <dt className="inline font-medium">なぜ変わった？ </dt>
                    <dd className="inline opacity-70">{c.why}</dd>
                  </div>
                )}
                {c.impact && (
                  <div>
                    <dt className="inline font-medium">私たちへの影響 </dt>
                    <dd className="inline opacity-70">{c.impact}</dd>
                  </div>
                )}
              </dl>
            </div>
          ))}
        </div>

        {explainer.faq.length > 0 && (
          <div className="pt-2">
            <h3 className="text-[14px] font-medium mb-3">よくある質問</h3>
            <div className="space-y-3">
              {explainer.faq.map((f, i) => (
                <div key={i}>
                  <p className="text-[14px] font-bold">Q. {f.q}</p>
                  <p className="text-[14px] leading-[24px] opacity-70 mt-0.5">
                    A. {f.a}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: ページに結線（import・metadata・描画）**

`frontend/app/law/[lawId]/page.tsx` を3箇所変更：

(a) import 追加（`BreadcrumbJsonLd` import の下、8行目付近）：

```tsx
import { LawExplainerSection } from "@/components/law-explainer";
```

(b) `generateMetadata` 内の `desc` 定義（現状21行目）を、`explainer.intro` 優先に変更：

```tsx
  const desc =
    data.explainer?.intro ||
    data.summary?.description ||
    `${data.law_title}の改正履歴を時系列で一覧。全${data.revision_count}回の改正について、いつ・どの条文が・どう変わったかをわかりやすく確認できます。`;
```

(c) 「この法律について」の summary カード（`{data.summary && ( ... )}` ブロック、現状102-150行）の**直後**に追加：

```tsx
      {data.explainer && (
        <LawExplainerSection lawTitle={data.law_title} explainer={data.explainer} />
      )}
```

- [ ] **Step 3: 型チェックとlint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: PASS（エラー・警告なし）

- [ ] **Step 4: Commit**

```bash
git add frontend/components/law-explainer.tsx frontend/app/law/[lawId]/page.tsx
git commit -m "feat: render LawExplainerSection on /law page"
```

---

## Task 7: 4法令の生成・事実性レビュー・ビルド検証

**Files:**
- データ生成: `data/timelines/{4法令}.json`, `frontend/public/data/timelines/{4法令}.json`

- [ ] **Step 1: 4法令で生成を実行**

Run:
```bash
uv run python scripts/explainer.py 416AC0000000123
uv run python scripts/explainer.py 129AC0000000089
uv run python scripts/explainer.py 322AC0000000049
uv run python scripts/explainer.py 335AC0000000105
```
Expected: 各コマンドが `Saved:` を表示して終了（VALIDATION FAILEDが出た場合は再実行、または当該記述を要確認）。

- [ ] **Step 2: 事実性レビュー（手動・必須ゲート）**

各JSONの `explainer` を開き、spec「事実性レビューゲート」に従い突合：
- 各 `recent_changes` の `year`/`title` が timeline の施行年・改正法名と整合。
- `grounded:true` の `why`/`impact` が当該 diff の `pr_summary` の範囲内。
- `faq` の回答に未確認の数値・期限の断定が無い。
- 問題があれば該当記述を手修正、または再生成。

Run（確認補助）:
```bash
for id in 416AC0000000123 129AC0000000089 322AC0000000049 335AC0000000105; do
  echo "=== $id ==="; python3 -c "import json;e=json.load(open(f'frontend/public/data/timelines/$id.json'))['explainer'];print(json.dumps(e,ensure_ascii=False,indent=2))"
done
```

- [ ] **Step 3: ビルド**

Run: `cd frontend && npm run build`
Expected: PASS（エラーなし）

- [ ] **Step 4: ビルド出力に見出し・本文が含まれることを確認**

Run:
```bash
cd frontend
for id in 416AC0000000123 129AC0000000089 322AC0000000049 335AC0000000105; do
  echo "=== $id ==="; grep -o '最近の改正をわかりやすく' "out/law/$id.html" | head -1 || echo "MISSING"
done
```
Expected: 各法令で `最近の改正をわかりやすく` がヒット。

- [ ] **Step 5: 後方互換の確認（explainer未生成の法令）**

Run:
```bash
cd frontend
# explainerを持たない任意の法令ページがビルドされ、セクションが無いこと
grep -L '最近の改正をわかりやすく' out/law/140AC0000000045.html && echo "OK: no section on non-target law"
```
Expected: `OK: no section on non-target law`（対象外法令にはセクションが無い）

- [ ] **Step 6: Commit**

```bash
git add data/timelines frontend/public/data/timelines
git commit -m "data: generate explainer for 4 Phase1 laws"
```

---

## Task 8: 本番反映

- [ ] **Step 1: push（Vercel自動デプロイ）**

Run: `git push origin main`
Expected: GitHubへ反映。Vercelが本番デプロイを開始。

- [ ] **Step 2: デプロイ完了と本番表示を確認**

Vercel MCP `list_deployments`/`get_deployment` で最新コミットの本番デプロイが READY になることを確認後：

Run:
```bash
curl -s https://lexdiff.com/law/416AC0000000123 | grep -o '最近の改正をわかりやすく' | head -1
```
Expected: ヒットする（本番反映済み）。

- [ ] **Step 3: 観測のメモ**

spec「成功条件・観測（Phase1）」に従い、2-3週間後にGSC/GA4で4法令の `/law` のクリック・CTR・対象クエリ順位を確認する旨をTODO/メモに残す。

---

## Self-Review チェック結果

- **Spec coverage**: データ構造(Task1)・集約と根拠付け(Task2,5)・検証(Task3)・正規化/faq正規化(Task4)・描画(Task6)・meta description(Task6 Step2b)・事実性レビューと自動検証(Task3,7)・成功条件の観測(Task8)・FAQ JSON-LDはスコープ外(実装せず=spec整合) — 各specセクションに対応タスクあり。
- **Placeholder scan**: TBD/TODO無し。各コード手順に実コードを記載。
- **Type consistency**: `select_changes`→`normalize_explainer`の`selected`要素キー(`year`/`source_title`/`grounded`)、`LawExplainer`/`ExplainerChange`(`why`/`impact` optional, `grounded` required)はTask1の型・Task6の描画(`c.why`/`c.impact`のoptional参照)と一致。`validate_explainer(explainer, valid_years)`のシグネチャはTask5 main呼び出しと一致。
