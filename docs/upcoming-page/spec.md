# 施行予定の法改正一覧ページ（/upcoming）— 仕様（Gate 1 grilling, 2026-10-18）

**要は**: トップの「施行予定の改正」欄（最大 5 件）を、検索から直接来られる独立ページ
`/upcoming` にする。#34 の「12月・1月に施行される改正」ハブ。データは出荷済みの施行前 diff
だけで、AI は使わない。日付・件数・名前はすべてデータから決定的に出す。

## 決定（ユーザー確定、Gate2 第1周で一部修正）

- Q1 1 ページ。施行日が確定しているものを月ごとの見出し「施行日が{Y}年{M}月の改正」で並べる
  （Gate2 L1: 「…に施行」は未来の出来事の断定）。**title / description に月を入れない**
  （Gate2 H2: 政令の期限日が紛れ込み、静的ページは月が過ぎても古い月を名乗り続ける。
  「12月から変わる法律」は本文の月見出しで受ける）。
- Q2 施行日が e-Gov 上で確定していないもの（どれかの revision に `enforcement_comment`）は月の
  見出しに入れず、最後の節「施行日が e-Gov 上で確定していない改正」に e-Gov の注記ごと並べる
  （Gate2 M1: 注記には「○○法の施行の日」もあり、政令とは限らない）。
- Q3 冒頭はトップと同じく「各行の日付の時点では未施行だった」で、1 つの日付を名乗らない
  （Gate2 H1: 最も古い生成日は、後から追加した法令について嘘になる）。各行に
  `asOfLabel(generated_on)`。日付を過ぎて未作り直しの diff（`isOverduePending`）は外す。
- Q4 各行: 法令名・`pendingName`（番号）・施行日（`enforcementLinesFor`）・`pendingStatsLabel`・
  diff ページへのリンク。
- Q5 未追跡の法律は範囲外。範囲を 1 行で明記する（Gate2 M2）:「lexdiff が収録する法令のみ。
  条文中の表が変わる改正は差分を作れないため載せていません」。

## 既にある仕組み

トップの施行前一覧（`app/page.tsx:71-76` の upcoming 抽出と `:223-250` の行）、`isPendingDiff`・
`isOverduePending`・`pendingName`・`enforcementLinesFor`・`asOfLabel`・`pendingStatsLabel`
（`lib/pending.ts`）、`mainChangeCounts`（`lib/data.ts`）。抽出はトップと共通の関数に寄せる。

## 不変条件

1. 載る diff の集合 = `isPendingDiff && !isOverduePending` の出荷 diff 全件。`<main>` 内で各 diff への
   `/diff/{id}` リンクはちょうど 1 本（行のリンク）。
2. 施行日確定の diff は `date_after` の先頭 7 文字（文字列で切る。タイムゾーンに依らない）の
   月節に入る。月節の集合 = 確定日の行の月の集合（空の節なし）。月は昇順、節内は日付→id 昇順。
   確定していない diff は最後の 1 節だけに入り、日付→id 昇順。その節は該当行があるときだけ出る。
3. 改正は年で呼ばない（`pendingName`）。月見出しは確定日の行にだけ付く。title / description に
   日付・月・年を入れない。
4. 各行の表示文に `asOfLabel(generated_on)`・`pendingName`・`enforcementLinesFor`・
   `pendingStatsLabel(mainChangeCounts(...).total)` がそのまま現れる。
5. 載る diff が 0 件でもビルドは通り、「現在、掲載できる施行予定の改正はありません」を出す。
6. sitemap に `/upcoming`。lastModified は載る行の `generated_on` の最大値（未来日にならない。
   0 件なら付けない）。トップの施行予定欄に `/upcoming` へのリンク（欄が出るときだけ）。
7. canonical `/upcoming`、openGraph の title / description / url を自前で持つ（Gate2 M3）。
8. 新しい文言・抽出・分類はすべて `pending.ts`。ページは `data-build-date` に `BUILD_DATE_JST` を出し、
   判定はその日付で行う（Gate2 H3: 日付をまたぐビルドと判定の食い違い）。
9. 出荷 diff の各 revision の `scheduled_enforcement_date` は null か `date_after` に等しい
   （Gate2 L2。複数 revision の diff を 1 つの日付で語る前提を CI で守る）。

## Gate2 第2周の反映（high 0。以下は medium/low の取り込み。これで確定）

- 文言（すべて `pending.ts` の定数・関数。判定は完全一致）:
  - title「施行予定の法改正一覧」、description・OG も固定文（数字・年月・和暦を含まない）
  - 冒頭「成立済みで、各行の日付の時点では未施行だった改正です。施行されると変わる条文を差分で確認できます（AIによる解説はありません）」
  - 範囲「lexdiff が収録する法令のうち、差分を作れた改正のみを載せています（e-Gov に施行日の記載がない改正や、条文中の表が変わる改正は載せていません）」（M7）
  - 月見出し「施行日が{Y}年{M}月の改正」（M は数値、0 埋めなし。L1）
  - 最後の節の見出し「各行の日付の時点で、施行日が e-Gov 上で確定していなかった改正」（M1: 日付なしの断定を避ける）
  - `unenforced_before` が空でない行は、件数に「（e-Gov 上の予定日の順で、先に施行予定の改正 N 件を反映した条文との比較）」を添える（M2）
  - 空状態「掲載できる施行予定の改正はありません」（L7: 「現在」を言わない）
- 目印（M3）: 節は `<section data-upcoming-section="YYYY-MM|unfixed">`、最初の `<h2>` が見出し。行は節の中の
  `<a href="/diff/{id}" data-pending-id>` で、4 つの文言はその `<a>` の中。ページ自身は `<main>` を描かない。
  `<main>` 内の `/diff/` リンク先の集合 = 期待集合（L4）。テキストは要素のテキストを連結して比べる（L2）。
- `data-build-date`（M4）: 判定は「≥ 載る行の最大 generated_on」かつ「HTML の更新日（JST）か前日」を確かめてから使う。
- sitemap の `/upcoming` に lastModified を付けない（M5: どちらの計算でも嘘になる場合が残る）。
- canonical と OG（url・title・description に加え site_name・locale・type を明示。L3）を判定する。
- トップのリンクは施行予定欄の中にあることを判定する（L8）。
- 誤り入り fixture は判定項目ごとに 1 つ（M6）。
- 判定スクリプトの実ページへの実行は手で行う（M8。CI の定義は変えない — 変更には別承認が要る種類の diff）。
- 不変条件 9 は施行日に注記がある revision のための検査（L6）。

## 非ゴール

月ごとの別ページ／未追跡法律の追加／AI の解説・要約／施行日を過ぎた後の自動の作り直し。

## 入口表

| # | 箇所 | 条件 |
|---|---|---|
| 1 | `frontend/app/page.tsx:71-76` upcoming 抽出（共通関数へ）／`:223-250` 欄にリンク | 1, 6 |
| 2 | 新 `frontend/app/upcoming/page.tsx`（metadata・canonical・OG・本文・data 属性） | 1-8 |
| 3 | `frontend/lib/pending.ts`（抽出・分類・並べ替え・文言） | 2-5, 8 |
| 4 | `frontend/app/sitemap.ts`（/upcoming と lastModified） | 6 |
| 5 | `tests/test_shipped_data.py`（scheduled_enforcement_date の一致） | 9 |
| 6 | `frontend/public/data/timelines/*.json`（表で差分の無い施行予定は載らない — 範囲文で明示） | Q5 |

## 受け入れ

判定スクリプト `scripts/check_upcoming_page.py`（コミット）が build 後の HTML を出荷データと
突き合わせる。目印の属性だけでなく**表示文**を見る: 各月節の見出し文、各行の 4 つの文言、
`<main>` 内の全 `/diff/` リンクの本数、節の集合と順序、空状態の文言、title / description に
年月が無いこと、sitemap の lastmod、トップのリンク。`--data-dir` と `data-build-date` を使う。
`tests/test_check_upcoming_page.py` に、正しい HTML と誤り 1 つずつの HTML（行の欠落・リンク重複・
確定していない行が月節に・見出し文の誤り・空の月節・title に月・空データで空状態の文言なし）を
置き、判定が赤になることを pytest で保つ。

```bash
(cd frontend && npm run lint && npm run build)
uv run python scripts/check_upcoming_page.py frontend/out
uv run pytest
```
