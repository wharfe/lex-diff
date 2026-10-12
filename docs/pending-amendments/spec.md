# 施行予定の改正を差分ページとして出す — 仕様（1ページ）

## 要は何

成立したがまだ施行されていない改正（e-Gov の `UnEnforced`、12 法令で 30 件）を、
施行済みと同じ「前日 → 施行日」の diff として公開し、「施行前」と明示する。
**AI の解説は付けない**（ユーザー確定）。動機: 安野氏の note は民法98条2項を「未改正」と
誤認した — 令和5年法律第53号で改正済み・施行待ちだった。lex-diff はその改正を出せる
（試作: 現行 → 2028-06-13 版で本則 20 条、98条を含む。表の変化なし）。

ユーザー確定（Q1–Q5）: 全件対象・表が変わる組は保留（#28）／トップの「最新」と目玉からは
外し小さな「施行予定」欄を設ける・サイトマップには載せる／施行日が動いたら URL が変わるのを
受け入れ、食い違いは機械で検出して人が作り直す／「施行前」はビルド時に JST で判定／
AI 生成への混入は Python で強制的に防ぐ。

## 既にある仕組みを探したか

探した。**新しい差分の仕組みは作らない。** `diff.py` の「前日 → 当日」組は未来日でもそのまま
働く（e-Gov `asof` は未来日で `UnEnforced` 版を返す — 2028-06-14 で実測）。積み重なった
施行待ちは前日の版が直前の施行待ち版になるので、改正ごとに分かれる。`timeline.py` は日付で
`diff_id` を組むので、出荷すれば自動でリンクされる。足りないのは **AI を通らない出荷経路**
（今は `annotate.py` が出荷を兼ねる）と、**施行日の確定度**という事実だけ。
CI に定期取得を足すのは CI 定義の変更＝(A) になるので採らない（Q3 の「CI で検出」は
「パイプラインの `--check` で検出」に読み替える。CI はネットに出ず鮮度を判定できない）。

## 不変条件（壊したら失敗）

1. **未確定の施行日を確定日として書かない。** e-Gov は未確定の改正に
   `amendment_scheduled_enforcement_date` と `amendment_enforcement_comment`
   （「政令で定める日」等）を付け、一覧の `amendment_enforcement_date` に予定日を入れる
   （実測: 予定日あり⇔コメントあり⇔`UnEnforced` のみ、22 件。残り 8 件の施行待ちは確定日）。
   施行前の画面では、未確定ならコメントを**原文のまま**出し予定日を「e-Gov 上の予定日」と
   添える。「遅くとも」等への言い換えはしない。施行年をタイトルに入れない（前倒しがありうる）
   — 施行前の名前は改正法番号（「令和五年法律第五十三号」）で付ける。
2. **施行前の差分を、施行済みの事実として書かない。** 「変更されました」等の過去形、
   「最新の改正」「最新のdiff」への混入、サイトマップの未来日 lastmod を出さない。
   既存の `sitemap.ts:49`（年表先頭＝2029-06-23 を lastmod にしている）も同じ根なので直す。
   **時点を書く（Gate2 で同根 2 回 → spec に戻した結論）**: 「施行前か」は時間で変わる状態で、
   静的ページは作り直すまで変わらない。現在形で「施行前」と言い切ると、日付を過ぎた瞬間に
   どの面かが嘘になる（政令の期限は施行日ではない／固定日なら施行済み — どちらに転ぶかは
   ページには分からない）。だから施行前 diff の主張は**すべて `generated_on` を主語にする**:
   タイトル・説明・見出し・件数・年表の印・トップの一覧すべてで「{generated_on} 時点で未施行」。
   この文は日付を過ぎても真のまま。日付を過ぎた施行前 diff はトップの「施行予定」から外し、
   見出しに「施行されたか・内容が変わったかは未確認」を添える。年表の印は「リンク先が `pending`
   を持つ」か「`enforcement_comment` を持つ」で立てる（diff ページと同じ根拠）。
   `articles.collect_changes` も `explainer.select_changes` も `pending` を持つ diff を根拠にしない。
3. **施行前の差分を AI の根拠にしない。** `annotate.py` は施行前の diff を拒否する。
   `explainer.select_changes` は施行日 > 今日（JST）の entry を `grounded=False` にする
   （`diff_id` があっても）。`articles.collect_changes` は既に除外している（`:83`）。
4. **鮮度は中身で判定する（Gate2 第3周で手段を交換・ユーザー確定）。** 施行待ちかどうか・
   予定日は、`pending.py` がその実行で取り直した `law_revisions` で決める（ディスク上の
   `_revisions.json` を信用しない）。`--check` は一覧を取り直し、前日・当日の版も取り直して
   **生成と同じ純関数で文書を作り直し、出荷物と中身で比べる**（`generated_on`・`proposer` を除く）。
   id や日付の一致で代用しない — e-Gov は施行待ちの本文を id を変えずに更新する（実測:
   `415AC0000000057_20261102_…` updated 2026-10-01）。出荷済みなのに作り直しで出なくなった
   （施行済み・日付変更・空・表変更）もの、まだ出荷していない施行待ちも報告して exit 1。
   削除・作り直しは人。施行前の版は `data/raw/pending/` に置き、`data/raw/` には書かない
   （`diff.py` が取得時刻を確かめずに読むため）。
   改正前の側（D-1 の版）は、D より前の施行待ちの改正を当てた版で、現行法ではない。
   `pending.unenforced_before` にそれらを記録し、画面に「改正直前の条文には、{generated_on}時点で
   未施行の次の改正も反映されています（順序は e-Gov 上の予定日による）」と出す。
5. **既存の diff の出力を変えない。** `diff.py` の切り出しで施行済み diff の JSON が
   1 バイトも変わらないこと（全出荷 diff の再生成と比較）。

## 非ゴール

AI 解説（pr_summary・条文注釈・explainer の why/impact）／条文ページへの施行予定の告知／
表の差分（#28）／施行日経過後の自動の作り直し（`--check` が知らせ、人が回す）／
CI での e-Gov 取得／既出荷 explainer の文面の再生成／explainer が施行前の改正に未確定の
予定年を書く既存の挙動（`explainer.py:53` `law-explainer.tsx:31`。出荷中の民法「2028年に施行
される予定」— PR 本文に残す）／`revision_count` が施行前を数える既存の挙動。

## 受け入れコマンド

```bash
uv run pytest                                      # 新規テスト込みで全件緑
uv run python scripts/pending.py --all             # 30 件を処理、表変更は保留と報告
uv run python scripts/pending.py --all --check     # 直後は exit 0
cd frontend && npm run lint && npm run build       # 施行前ページが生成される
```
目視: `/diff/129AC0000000089_2028-06-12_2028-06-13` に「施行前」・コメント原文・
98条の差分、トップの「最新」に施行前が出ない、`/law/129AC0000000089` の年表で印とリンク。

## 入口表（不変条件が破れうる場所）

| # | 場所 | 行 |
|---|---|---|
| 1 | `frontend/app/diff/[diffId]/page.tsx:26,35` | `year = data.date_after.slice(0, 4)` ／ `【${year}年改正】` |
| 1 | `frontend/components/revision-header.tsx` | 施行日の表示（実装時に読む） |
| 1 | `frontend/components/timeline.tsx:36,70` | `{entry.enforcement_date}` ／ 公布日と施行日の比較 |
| 2 | `frontend/app/diff/[diffId]/page.tsx:33` | `本則${mainCount}条が変更されました` |
| 2 | `frontend/app/page.tsx:56,59` | `date_after` 降順の「最新」／目玉＝変更最多 |
| 1 | `frontend/app/diff/[diffId]/page.tsx:41,75` | OG title の `【${year}年改正】` ／ パンくず `data.pr_summary?.title \|\| data.date_after` |
| 1 | `frontend/components/revision-header.tsx:43` | `date_before` チップ（未確定日の前日） |
| 2 | `frontend/app/theme/[themeId]/page.tsx:89,127` | 年表の先頭の diff を「最新の差分」として拾う |
| 2 | `frontend/components/diff-stats.tsx:79` | 「本則 N 条が変更」 |
| 2 | `frontend/components/diff-viewer.tsx:218,224` | `note="法律の中身が変わった条文"` |
| 2 | `frontend/app/sitemap.ts:22-25,49,60` | `latestDiffDate` ／ `timeline[0].enforcement_date` ／ `data.date_after` |
| 3 | `scripts/annotate.py:383` | `main()` — 出荷を兼ねる。施行前を拒否する場所 |
| 3 | `scripts/explainer.py:44-48,57` | 同名タイトルの重複除去が `diff_id` 有りを優先 ／ `"grounded": bool(c["diff_id"])` |
| 3 | `scripts/articles.py:83` | `if doc["date_after"] > today:`（既に安全） |
| 4 | `scripts/diff.py:513-523` | `_revisions.json` をディスクから読む |
| 4 | `scripts/timeline.py:87,113-120` | 一覧の施行日で `diff_id` を組む |
| 5 | `scripts/diff.py:452-` | `main()` を関数へ切り出す場所 |
| — | `scripts/enrich.py:79` ／ `tests/test_shipped_data.py:30` ／ `frontend/lib/data.ts:10` | 全 diff を列挙（施行前も拾う。提案者・統計テストは施行前でも成り立つべき） |
