# #26 墓標ページの「改正直前の条文」と最新カードのラベルを結ぶ — 仕様（1ページ）

## 要は何

条文ページの「今回の改正直前の条文」ブロック（`former` が非 null なら出る）と、改正履歴の
いちばん上のカードの「改正直前／改正直後」ラベル（`changes[0].summary_basis`）は、別々の根拠から
作られていて、互いを確かめていない。食い違うと読者には「改正直前の条文についての説明」とだけあって
当の条文が無い（またはその逆の）半端なページが届き、壊れた表示にはならないので誰も気づかない。
**保存前に `validate_articles()` で両者を結び、崩れたら非ゼロで止める。** 出荷データにも同じ検査を
独立に掛ける。2026-10-14 実測: 12 法令 422 ページ 460 改正、`former` 非 null = 最新 before = 6
（民法733・746・753・754、刑法13・178）、不整合 0。

## この機能を既に持っている仕組みはないか

- `validate_articles()` が保存前の唯一の関所で、出荷バイトにも `test_shipped_articles_pass_validate_articles`
  で掛かっている。足すのはこの関数の中（新しい仕組みは作らない）。
- 「片方からもう片方を導いて食い違いを消す」案（フロントで `former` の有無からラベルを決める等）は採らない。
  両者は独立した事実（最新 diff の改正後本文／今日の本文が墓標か）から来ていて、食い違いは
  **diff が今日の本文に追いついていない**ことを意味する。片方に合わせると、その事実ごと隠れる。

## 不変条件（壊したら失敗）

1. **ページごとに `former is not None` ⇔ `changes[0].summary_basis == "before"`。** 両方向とも
   エラー文を分けて返す。`former` の有無は Issue の言い方どおり `is not None`（生成側は null か
   段落つきの dict しか作らない）。見えるラベルではなく**データ**を検査する: ラベルは
   `plain_summary` が空だと出ない（article-history.tsx:26、`_card_summary` が空にしうる）が、
   その場合も食い違い自体は「diff が今日の本文に追いついていない」ことなので止める（意図的に厳しい）。
2. **「最新の改正」は `changes[0]`。** 今のコードの定義そのもの: `collect_changes()` が施行日の
   降順に（安定ソートで）並べ、`build_law_articles()` が `latest = history[0]` から `former` を作り、
   同じ順で `changes` を書く。フロントは配列順に描くので、読者にとっての「いちばん上のカード」も
   `changes[0]`。加えて**多重防御として `changes` が施行日の降順（同日は許す）であることも検査する**
   （最新の diff が抜けていないことまではこれでは分からない — それは不変条件 4 の照合が担う）。
3. `validate_articles()` は例外を出さずにリストを返す（既存の姿勢）。`changes` が空、または
   `changes[0].summary_basis` が不正なときは既存の検査がエラーを出しているので、新しい対応検査は飛ばす。
   施行日が無いか文字列でない改正があれば「a change's enforcement_date is missing or not a string」を出し、
   並び順検査は飛ばす。
4. 出荷データ側の検査は `validate_articles()` を呼ばずに**出荷 diff から導き直す**:
   `collect_changes(shipped diffs, そのファイルの source.asof)[num][0]` を最新とし（実時計は使わない —
   使うと pending が作り直された日に偽の赤になる）、ページの `changes[0]` がその diff であること、
   そのラベルが本文から決め直した値と同じこと、`former` の有無がそれと一致すること、`former` があれば
   その `as_of` と段落が最新 diff の `date_before` / `paragraphs_before` と同じことを見る。
   判定は `(article_doc, diff_docs)` を取る helper に置き、メモリ上でページ側と diff 側の両方を崩して
   分岐ごとに赤になる恒久テストと、全ファイル横断で before のページが空でないことのテストを添える（空振り防止）。
5. 出荷データ（`frontend/public/data/`）と `data/` は変えない。今のデータは新しい検査を全部通る。

## 非目標

- `former` があるのに墓標でないページの検出（`build_law_articles` は墓標にしか作らない。#26 の範囲外）
- `validate_articles()` での `former` の中身と最新改正の照合（ページの `changes` に `date_before` が無い。
  出荷テストは最新 diff を持つので照合する）
- `former` の形の検査（`false` や `{}` のような値。生成側は作れず手編集でしか起きない）
- 出荷テストで履歴全体の (diff_id, ラベル) を照合すること（#26 は最新カードと former の対応だけ）
- フロントエンドの変更、データの再生成、他の検証器の変更

## 入口表（この不変条件が壊れうる場所）

scout 2 本（読み取りのみ）で列挙し、534・563–567・609・876 は自分で確認した。

| 場所 | 何をしているか | 不変条件 |
|---|---|---|
| `scripts/articles.py:106` | `summary_basis(paragraphs_after)` を各改正に付ける（本文で決まる） | 1 |
| `scripts/articles.py:122` | 施行日だけをキーに降順ソート（同日は追加順＝diff ファイル名順 :762） | 2 |
| `scripts/articles.py:86–100` | 未施行・pending・附則・範囲の改正を並べる前に落とす（どれが最新かが変わる） | 2 |
| `scripts/articles.py:534` | `latest = history[0]` | 2 |
| `scripts/articles.py:254, 283` | 墓標かどうかを今日の本文で決める | 1 |
| `scripts/articles.py:563–567` | 墓標かつ `paragraphs_before` があるときだけ `former` を作る | 1 |
| `scripts/articles.py:597, 609, 627` | `former` と、`history` 順の `changes`（ラベル付き）をページに書く | 1, 2 |
| `scripts/articles.py:746–751` | 既存: 墓標なら `former` 必須・現在の解説なし | 1–3 |
| `scripts/articles.py:753–779` | 今回足した検査（日付・並び順・former と最新カードの対応） | 1–3 |
| `scripts/articles.py:903–908` | 検証エラーなら exit 2、何も保存しない | 1–3 |
| `scripts/articles.py:921–922` | 出荷ファイルを書く唯一の場所（他スクリプトに書き手なし） | — |
| `frontend/.../page.tsx:100` | `article.former &&` でブロックを描く（オブジェクトなら描く） | 1 |
| `frontend/components/article-history.tsx:17, 26, 44` | 配列順に描き、`plain_summary` があるときだけラベルを出し、`"after"` 以外は 改正直前 | 1, 2 |
| `scripts/articles.py:355–375` | `_card_summary` がカードの `plain_summary` を空にしうる（ラベルが見えなくなる） | 1 |
| `tests/test_shipped_data.py:172, 201` | 出荷バイトに validate を掛ける／最新を `collect_changes()[num][0]` で導き直す前例 | 4 |

同じ法令で施行日が同じ diff は今の出荷物に無い（ファイル名で確認）。あっても安定ソートなので
`build` と `changes[0]` は同じものを指し、降順検査は同日を許す。

## 計画（Gate 2 第1周: high 以上 0。medium 3・low 4 を取り込み済み）

1. 赤: `tests/test_articles.py` に、名前に `latest_card` を含むテストを足す。`_build` 経由（実際の
   組み立て経路）で両方向の食い違い — 既存エラーが出ない形（今日も本文がある条に「削除」の最新 diff／
   墓標に本文つきの最新 diff）— を組み、エラー一覧の**完全一致**で拒否を見る。正常対応 2 種の通過、
   複数 diff を `collect_changes` に通して最新だけを見ること、組んだ doc の `changes` を手で逆順に
   すると拒まれること、同日の許容、施行日欠落で例外にならないこと。生成入口 `main()` を
   既存の差し替え（e-Gov に出ない）で通し、食い違いで exit 2・どちらの写しも書かないこと。
   `tests/test_shipped_data.py` に不変条件 4 の helper とテスト 3 本（各ファイル・横断・崩した doc）。
2. 緑: `validate_articles()` に不変条件 1–3 を足す（十数行）。

## 受け入れコマンド

```bash
uv run pytest -q                                          # 全体が緑
uv run pytest -q tests/test_articles.py -k latest_card    # 新規分（実装前は赤）
uv run pytest -q tests/test_shipped_data.py -k former     # 出荷バイトに対する検査（崩した doc の赤を含む）
git status --short -- frontend/public/data                # 出力なし（data/ は gitignore なので git では見えない。articles.py は走らせない）
```

## Gate 3 第1周で足したもの

- 既存 `test_validate_rejects_an_enforcement_date_after_the_asof` の断言を文面の完全一致に（新しい日付エラーにも
  `enforcement` が入り、検査本体を消しても緑のままだった — 突然変異で確認）
- main() テストは出力されたエラー文まで見る。日付欠落は最新カードと古いカードの両方・4 種の値で見る。
  空の履歴・不正なラベルで対応検査が重ねてエラーを出さないことを固定
