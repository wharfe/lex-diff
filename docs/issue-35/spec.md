# #35 explainer の項目の単位 — 確定仕様（Gate 1 + Gate 2 第2周で手段を交換, 2026-10-18）

**要は**: explainer（/law の「最近の改正」）の 1 項目を「改正法 1 本」から
**「本則が変わった施行 1 回（= 出荷済みの施行済み diff 1 つ）」**に替える。AI はその日に
何が変わったかだけを、その diff の要約から書く。根拠なしの項目（名前と年だけ）は廃止。

## なぜ手段を替えたか

元の不具合: 名前で改正法を畳み（13 法令中 11 で別の改正法が 1 件に）、施行前の改正を根拠なしで
渡し、公益通報者保護法で 2022 年改正が消え「大きな変更はない」と書いた。
「改正法の番号で畳む」で直そうとしたところ、Gate2 で同じ根の指摘が 2 周続いた — 附則だけの
段が改正法の代表になり「本則／中身は変わらない」を根拠に渡す（第1周 H1・第2周 H2、刑法
507AC…039 で新設罪が消える）、外した改正法が共有 diff と同日の名前から漏れる（第2周 H1、
著作権法）。根は**説明の単位（改正法）と根拠の単位（施行 1 回の diff、複数法で共有あり）の
食い違い**で、「改正法 = 1 項目」は目的ではなく手段由来の制約だった（ユーザー確定）。

## 決定（ユーザー確定）

- 項目 = 施行済み・本則変更ありの diff。施行前の改正は AI に一切渡さない。
- 画面は explainer の下に固定文「{generated_on}時点で施行済みの改正が対象です。施行予定の
  改正は改正履歴をご覧ください。」（文言は `frontend/lib/pending.ts`）。
- 将来の施行を主張する文を検証で落とす。
- 全法令の explainer を作り直す。項目が 0 件の法令は explainer を持たない。

## 既にある仕組み

施行前判定 `is_pending_entry`（`scripts/explainer.py:25`）、diff の `stats.main`
（`diff.compute_stats`、本則のみ）、diff が自分の改正法を名乗る `amendment_law_titles` と
`apply_diff` の多法令処理、文言の置き場 `pending.ts`、`jpDate`。新しい判定は作らない。

## 不変条件

1. **項目の元**: timeline の entry のうち `diff_id` を持ち、`is_pending_entry` が偽のもの。
   diff_id で重複を除き、diff を読んで `pending` キーなし・`stats.main > 0` のものだけ。
   施行日の新しい順に `MAX_CHANGES`（4）件。読めない diff は raise（黙って落とさない）。
2. **名前は diff から**: 項目の改正法名は `apply_diff` が diff から決める（既存）。timeline の
   名前で畳む処理（`by_title`）は削除。
3. **プロンプト**: 各項目は「{施行日}の施行分」として渡し、ルールに足す —
   その日の変更だけを書き、改正法全体や、他に変更がある／ないことを述べない／
   intro は渡した項目の要約に限る／根拠要約の未来の表現を写さない／「予定」「見込」を使わない。
4. **形の層** `validate_explainer_shape(explainer)`（根拠不要。生成時と CI の両方で走る）:
   (a) `generated_on`（YYYY-MM-DD）と各 recent_change の `diff_id` がある、
   (b) 全文（intro / title / what / why / impact / faq q・a）に「予定」「見込」がない、
   (c) 西暦「NNNN年」、「令和N年」（算用・漢数字、=2018+N）が generated_on の年を超えない
       （施行済みの法の期限も落としうる — fail-closed を選ぶ）。
5. **出荷物の検査（CI, `tests/test_shipped_data.py`）**: 出荷済み explainer の各 `diff_id` が
   出荷 diff として存在し、`pending` キーを持たず、`stats.main > 0`、施行日 ≤ generated_on。
6. 項目 0 件 → `explainer` キーを削除して保存（exit 0、そう表示）。検証失敗 → exit 2 で
   何も保存しない（既存）。作り直しで timeline の `explainer` 以外は 1 バイトも変えない。
7. explainer を出すページには必ず固定文が出る。

## Gate2 第3周の反映（周回上限。以降は検算で閉じる）

- H1 表の変化を検出する前に出荷された diff が 2 件、表の変化を見ないまま根拠になる
  （`335AC0000000105_2026-03-31_2026-04-01`、`415AC0000000057_2025-03-31_2025-04-01`。
  後者の要約は「制度の内容…に変更はありません」）→ 不変条件 1 に追加: `main()` は候補の各 diff
  について `data/raw/<law>_<date>.json` の前後で `diff.tables_changed` を呼び、真なら除外、raw が
  無ければ raise。CI 用に既知の 2 件を `diff.SHIPPED_WITH_TABLE_CHANGES` に置き、不変条件 5 で
  explainer の diff_id がそこに無いことを見る。
- M1 recent_changes の件数 = 選んだ件数（生成時）、explainer 内の diff_id 重複なし（形の層）。
- M2 pr_summary の無い diff は raise（`apply_diff` の黙った格下げを廃止）。
- M3 受け入れの比較基準は `2e0c954` に固定（HEAD ではない）。
- M4 CI: explainer を持つ法令の集合 = 出荷データ上で対象 diff が 1 件以上ある法令の集合。
- L1 画面は年でなく施行日を出す（各項目に `enforcement_date` を保存）。
- L3 4(b)(c) は NFKC 正規化してから見る。「見込」は条文由来の語でも落ちる — fail-closed。
- L5 同日名の収集は同じ diff_id の entry に限る。L6 `generated_on` は選定の today と同じ値。
- L2 「改正法全体を述べない」はプロンプトでしか守れない — 手順 3 の目視の観点にする。
- L4（施行前に diff.py で作った diff に pending 印が無い）は現データに該当なし。非ゴール。

## 実装中の決定（2026-10-18、ユーザー確定）

全法令を作り直して読んだところ、導入文と FAQ が渡した項目の外まで一般化した
（個人情報保護法・著作権法「制度の仕組み自体は大きく変わらない」）。プロンプトの規則では
2 回の生成とも止まらなかった。→ **AI は項目ごとの what/why/impact だけを書く。**
explainer は `{generated_on, recent_changes}` だけを持ち、導入は `pending.ts` の
`explainerIntro`（固定文）、meta description は法令概要（summary）に戻す。

Gate3 で、将来の日付を見分ける検査に表記の抜けが 2 周続いた（code-review: 同年の未来日付・
括弧併記・漢数字西暦／codex 再レビュー: 令和の月日・括弧併記の月日・漢数字の月日）。同じ根
（表記の列挙）なので手段を替えた（ユーザー確定）: **AI の文には日付・年を一切書かせない**。
不変条件 4(c) は「文中に年・月・和暦の日付が 1 つもない（期間・数は除く）」に置き換わる。
あわせて Gate3 で、モデル出力の件数を正規化前に数える検査と、「過料」を書いた文ごとに
根拠の「正当な理由」を保つ検査を足した（codex）。

## 非ゴール

表の差分（#28。表で保留中・表が変わった diff の改正は解説に出ない）／附則だけの改正の解説（労基 附則第138条
などは年表と diff ページに残る）／施行予定の解説／年表・施行前 diff ページの文言変更／
`law_summary`・`annotate` の変更／frontend 型の `grounded` の撤去（常に true で出す）。

## 入口表

| # | 箇所 | 条件 |
|---|---|---|
| 1 | `scripts/explainer.py:40-96` `select_changes`（全面書き換え。docstring 含む） | 1,2 |
| 2 | `scripts/explainer.py:200-230` `load_diff` / `apply_diff` | 1,2 |
| 3 | `scripts/explainer.py` `build_prompt`（根拠なし分岐の削除、ルール追加） | 3 |
| 4 | `scripts/explainer.py` `normalize_explainer`（diff_id・generated_on を付ける） | 4,5 |
| 5 | `scripts/explainer.py` `validate_explainer` / 新 `validate_explainer_shape` | 4 |
| 6 | `scripts/explainer.py` `main()`（0 件時の削除、generated_on = today_jst、同日名の収集） | 6 |
| 7 | `tests/test_explainer.py` 全体（fixture と施行前・根拠なし前提のテスト） | 1-6 |
| 8 | `tests/test_diff_same_day.py:106-140` `apply_diff` / `build_prompt` のテスト | 2,3 |
| 9 | `tests/test_shipped_data.py`（explainer 検査を追加） | 4,5 |
| 10 | `frontend/components/law-explainer.tsx`・`frontend/lib/pending.ts`・`frontend/lib/types.ts` | 7 |
| 11 | `frontend/app/law/[lawId]/page.tsx:50` meta description に intro（変わる。許容） | — |
| 12 | `CLAUDE.md` AI-Generated Content（grounded/ungrounded・dedupe by title の記述）／`docs/pending-amendments/spec.md:46-48,69-70,100`（旧挙動に注記） | 文書 |
| 13 | 出荷済み `frontend/public/data/timelines/*.json` の `explainer`（12 法令） | 4-6 |

## 手順

1. テストを先に赤: 施行前・pending diff・本則 0 の diff は項目にならない／共有 diff は 1 項目
   で diff の名前／4 件で切る／形検査（予定・見込・未来年 算用と漢数字・欠落）／0 件で削除。
2. 実装して緑（出荷物の検査は作り直すまで赤 — 3 で緑）。
3. 12 法令＋公益通報者保護法を作り直し、文を 1 本ずつ読む。
4. 固定文・型・文書。build。

## 受け入れコマンド

```bash
uv run pytest                                  # 全緑（出荷物の explainer 検査を含む）
(cd frontend && npm run build)                 # exit 0
uv run python - <<'EOF'                         # explainer 以外の差分なし（13 件を比べる）
import json, subprocess, pathlib, sys
fs = sorted(pathlib.Path("frontend/public/data/timelines").glob("*.json")); assert len(fs) == 13
for f in fs:
    old = json.loads(subprocess.run(["git", "show", f"2e0c954:{f}"], capture_output=True, check=True).stdout)
    new = json.loads(f.read_text()); old.pop("explainer", None); new.pop("explainer", None)
    if old != new: sys.exit(f"DIFF {f}")
print("ok", len(fs))
EOF
```
