# 条文ページに「この条文の最後の変更」を出す（#44）

## 要は何

条文ページで、現在の条文の直下に次の 2 つを出す。

1. 1 行: 「{asof}時点のこの条文の本文は、{施行日}施行の改正で今の形になりました。」
   - 続けて「この日の改正の全体を見る →」（`/diff/<diff_id>#<article_num>`）
   - 「本文」と書くのは、見出しの変更が差分にも判定にも出ないため（`diff.py:150` で見出しが条番号に上書きされる）
   - 「この日の改正」と書くのは、1 つの差分に改正法が複数ある場合があるため（刑法 2025-06-01）
2. その日のこの条文の行単位の差分

## 既にある仕組み（探した結果）

- 差分: 差分 JSON の各条文エントリに行単位の `diff` がある。描画は `DiffLine`（`frontend/components/diff-viewer.tsx:8`）を使い、新しく計算しない
- 版の判定: `texts_match`（`scripts/articles.py:326`）。表（`[表]`）と空の本文では不一致の側に倒れる
- 行内で変わった語を強調するライブラリは frontend に無い（今回は作らない）

## データ

`articles/<law_id>.json` の各ページに `latest_change: { diff_id, enforcement_date } | null` を足す。

- 差分の行は写さない。画面のビルド時に `diff_id` の差分 JSON を読み、本則のエントリを `article_num` で引く
  - 写すと、#28 で差分を作り直したときに古い写しが残る（作り直しにはネットワークが要る）
  - エントリが見つからなければビルドを失敗させる
- `changes[0]`（`collect_changes` が返す最新の改正）から作る

## null にする条件（どれか 1 つでも当てはまれば null）

| # | 条件 | 理由 |
|---|---|---|
| N1 | 削除済みの条文（`TOMBSTONE_STATUSES`） | 今の本文が無い |
| N2 | `texts_match(changes[0].paragraphs_after, current.paragraphs)` が偽 | その後の改正で本文が変わっている |
| N3 | `changes[0].diff_id` が `diff.SHIPPED_WITH_TABLE_CHANGES` に入っている | 表の変更が漏れた差分で、「全体」と呼べない（10 ページ） |
| N4 | 同じ差分の別の本則エントリと本文がつながっている（条の移動） | 繰り下げられた条が「新設」「全文の入れ替え」に見える（著作権法42条の4: `added` だが本文は旧42条の3） |

N4 は 2 つの判定のどちらかで null にする。どちらも、迷ったら「移動」の側（表示しない側）に倒す。

- 本文の類似: このエントリの改正後の本文と、同じ差分の別の本則エントリの改正前の本文の類似度が 0.9 以上（逆向きも同じ）
  - 完全一致にしないのは、繰り下げと同時に「前条」などの参照も書き換わるため
  - その類似度が、**両方の条それぞれの改正前後の類似度を上回る**ときだけ移動とみなす。並行する罰則（刑法246条 詐欺・249条 恐喝、26条の3・27条の6）は互いに 9 割似ているが、どちらも自分自身により似ている
- 変更行の一致: このエントリの 16 字以上の削除行の半分以上が、別のエントリが**追加した行**と一字一句同じ（追加行と削除行の組も同じ）
  - 別の条の本文全体とは比べない。前からあった共通の言い回しを移動と取り違えるため（Gate3 で codex が指摘）
  - 著作権法42条（2024-01-01）は、第2項が42条の2へ移ったのに削除に見える。これを拾う

比べる本文は「項の text を `_normalise` して改行でつないだもの」で、項番号は比べない。空の側、「削除」、16 字未満の本文は何とも一致させない。空を一致に数えると、民法 2026-04-01 の新設条 7 件（共同親権）が削除条の空と一致して消える。

出荷データでは 14 ページが N4 で null になる（`tests/test_shipped_data.py` の `EXPECTED_MOVED` に固定）。表示は 401 ページ。

## 不変条件

| # | 不変条件 |
|---|---|
| I1 | `latest_change` が非 null ⇔ N1〜N4 のどれにも当たらない |
| I2 | `latest_change` は `changes[0]` と同じ `diff_id`・`enforcement_date`。参照先の差分 JSON に、その `article_num` の本則エントリがちょうど 1 つあり、その `diff` には `---`・`+++` を除いて `-` か `+` で始まる行が 1 行以上ある |
| I3 | 画面は `latest_change` と `source.asof` を表示するだけ。日付を計算し直さず、改正法の名前も出さない |
| I4 | 施行前の差分（`pending`）は `latest_change` にならない |

## 変更が要る場所

| 場所 | 関わる条件 | 内容 |
|---|---|---|
| `scripts/articles.py:85` | I4 | `pending` の差分を除く（既存、変更なし） |
| `scripts/articles.py:103` | N4 | `collect_changes` が、同じ差分の本則エントリの本文を判定に使えるようにする |
| `scripts/articles.py:540` | N1, N2 | 既存の判定 |
| `scripts/diff.py:390` | N3 | `SHIPPED_WITH_TABLE_CHANGES` |
| `scripts/diff.py:233` | N4 | 条番号で突き合わせるので、繰り下げが全文の入れ替えに見える（原因、変更なし） |
| `scripts/articles.py:585` | I1, I2 | 出荷する形 |
| `scripts/articles.py:691` | I1 | `validate_articles`（削除済みなら null） |
| `tests/test_shipped_data.py:185` | I1, I2 | 出荷データで N1〜N4 と参照先をやり直す |
| `frontend/lib/types.ts:260` | I3 | 型 |
| `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx:110` | I2, I3 | 差分 JSON を読み、`ArticleText` の直後に置く |
| `frontend/components/diff-viewer.tsx:8` | — | `DiffLine` を export し、条文ページのときだけ効く引数で `@@` 行を区切り線にする（差分ページは今のまま） |
| `frontend/lib/data.ts:21` | — | `getDiffData` は呼ぶたびに読み直すので、差分 ID ごとに 1 回だけ読む |

## 非ゴール

- 行内の強調（次の PR）
- `<title>` と meta description の変更（#40 の測定日 11/20 以降に別の PR）
- 差分ページの見た目の変更
- 判定を通らないページに代わりの文を出すこと
- 項の番号を差分の行に出すこと（`diff.py` が出していない）

## 受け入れコマンド

```bash
uv run pytest
uv run python scripts/articles.py --all
cd frontend && npm run lint && npm run build
grep -c '今の形になりました' out/law/140AC0000000045/article/68.html        # 1
grep -c '今の形になりました' out/law/345AC0000000048/article/42-4.html      # 0（N4）
grep -c '今の形になりました' out/law/335AC0000000105/article/88.html        # 0（N3）
```

## 効果測定

GA4 で、条文ページの平均滞在時間と、条文ページから `/diff` への遷移の割合を、公開の前後 4 週間で比べる。
