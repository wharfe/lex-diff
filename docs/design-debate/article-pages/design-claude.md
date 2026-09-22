# 条文ページ — 設計案 A

brief §3 は動かさない前提で「どう作るか」を書く。brief §9 の6論点に全部答える。

## 0. 実データを開いて分かった、設計を変える事実

1. **民法第754条（夫婦間の契約の取消権）は 2026-04-01 に削除されている。**
   GSC で名前が見えている実クエリの1つが
   「e-gov 法令検索 民法 第754条 夫婦間の契約の取消権」。
   現在の e-Gov でこの条文を引くと「第七百五十三条及び第七百五十四条 削除」としか出ない。
   **削除条文は除外すべき例外ではなく、この機能が e-Gov に最もはっきり勝てる一枚。**
   削除前の条文・いつ削除されたか・なぜ、を出せるのは lex-diff だけ。
   観測できた 4 クエリのうち 1 つがここを指している。
2. **`article_num` に範囲形が実在する**: `"753:754"`（e-Gov の Article@Num が
   「第七百五十三条及び第七百五十四条」を1ノードで表す）。
   全165エントリ中: 数字のみ115 / アンダースコア49（`308_2` = 第308条の2）/ 範囲1。
   素直に article_num ごとにページを作ると、誰も検索しない `/article/753:754` が生まれる。
3. **複数改正を持つ条文は164件中1件だけ**（道路交通法 `117_2_2`、2024-11-01 と 2026-04-01）。
   稀だが実在するので、データ構造は最初から複数前提にする。1件だから特別扱い、にしない。
4. **`type: "deleted"` は2件のみ**（民法753・754）。両方 2026-04-01。

## 1. 方針

- **新しい取得器も、新しい木の走査も書かない。** brief §7 の通り、
  `fetch.fetch_law_data` / `lawtext.extract_text` / `lawtext.walk_tags` と、
  `diff.py` がすでに持っている条文の読み取り（`find_articles`・`article_to_lines`・
  `format_paragraph`・`format_item`）を使う。
- ただし後者は今 `diff.py` にある。**`lawtext.py` へ移す**。
  `lawtext.py` の冒頭コメントが明示している通り、この repo は
  「3つの生成スクリプトがそれぞれ自分のコピーを持ったせいで乖離した」のを
  一度やっている。4つ目のコピーを作らない。
- LLM は呼ばない。既存 `annotation` を組み替えるだけ。

## 2. データ生成側

### 2.1 新規: `scripts/article_pages.py`

`uv run python scripts/article_pages.py <law_id>` で1法令ぶんを生成する。
既存の `timeline.py` / `law_summary.py` と同じ粒度（法令単位）。

責務の分割:

| 関数 | 責務 |
|---|---|
| `collect_revisions(law_id, data_dir)` | その法令の全 diff JSON を読み、条番号 → 改正エントリの一覧を作る。附則は捨てる。範囲形を展開する（§2.3） |
| `fetch_current_articles(law_id, today)` | `fetch_law_data(law_id, today)` を呼び、`find_articles` で条番号 → 現在の条文ノードの辞書を作る。失敗は raise |
| `build_article_page(num, revisions, current)` | 1条文ぶんのレコードを組む。`current` が無ければ `status="deleted"` |
| `main()` | 上を繋ぎ、JST の日付を検査して保存する（§3） |

### 2.2 出力: `frontend/public/data/articles/<lawId>.json`

法令ごとに1ファイル。条文ごとに1ファイルにしない（164ファイルは扱いづらく、
既存の `timelines/<lawId>.json` と粒度が揃わない）。

```json
{
  "law_id": "129AC0000000089",
  "law_title": "民法",
  "asof": "2026-09-22",
  "fetched_at": "2026-09-22T10:33:14+09:00",
  "articles": [
    {
      "article_num": "306",
      "slug": "306",
      "heading": "第三百六条",
      "caption": "（一般の先取特権）",
      "section_path": ["第二編　物権", "第八章　先取特権", "第二節　先取特権の種類", "第一款　一般の先取特権"],
      "status": "current",
      "current_lines": ["第三百六条", "次に掲げる原因によって生じた債権を有する者は、…", "　一", "　共益の費用", "…"],
      "plain_summary": "特定の種類の債権を持つ人が、債務者の全財産から優先的に…",
      "revisions": [
        {
          "date": "2026-04-01",
          "type": "modified",
          "diff_id": "129AC0000000089_2026-03-31_2026-04-01",
          "amendment_law_title": "民法等の一部を改正する法律",
          "change_description": "これまでは「共益の費用」…今回の改正により、新たに「子の監護の費用」が…"
        }
      ],
      "cross_references": [
        {"ref": "第三百八条の二", "article_num": "308_2", "slug": "308-2", "has_page": true, "context": "子の監護の費用の先取特権が及ぶ範囲を定めた条文"}
      ]
    },
    {
      "article_num": "754",
      "slug": "754",
      "heading": "第七百五十四条",
      "caption": null,
      "section_path": ["第四編　親族", "第二章　婚姻", "第二節　婚姻の効力"],
      "status": "deleted",
      "deleted_on": "2026-04-01",
      "current_lines": [],
      "former_lines": ["第七百五十四条", "夫婦間でした契約は、婚姻中、いつでも、夫婦の一方からこれを取り消すことができる。ただし、第三者の権利を害することはできない。"],
      "plain_summary": "夫婦が結婚している間に交わした約束（契約）を、あとから一方的に取り消すことができるというルール",
      "revisions": [
        {"date": "2026-04-01", "type": "deleted", "diff_id": "129AC0000000089_2026-03-31_2026-04-01", "amendment_law_title": "民法等の一部を改正する法律", "change_description": "…この規定が削除されました。これにより…"}
      ],
      "cross_references": []
    }
  ]
}
```

キーの根拠:

- `current_lines` は `article_to_lines` の出力形（既存 diff の `lines_after` と同じ形）。
  フロントに新しい整形規則を持ち込まないため、既存と同じ表現にする。
- `former_lines` は削除条文だけが持つ。`type:"deleted"` エントリの `lines_before`。
- `plain_summary` は最新改正の `annotation.plain_summary`。
  条文が「何をする条文か」は改正で変わりうるので、最新を採る。
- `revisions` は日付の降順。**必ず配列**（1件しか無い条文でも配列）。
- `has_page` は cross_reference の指す条文がこの法令のページ集合に居るか。
  居なければリンクにしない（404 を作らない）。

### 2.3 範囲形 `753:754` の扱い

**範囲エントリ自体はページにしない。** `collect_revisions` が `:` を含む
`article_num` を各条番号へ**展開**し、その改正エントリを両方の条文の
`revisions` に入れる。`753:754` の `annotation.change_description` は
753 と 754 の両方について書かれているので、そのまま両方に載せて意味が通る。

結果: 民法 753 と 754 のページはそれぞれ
「削除エントリ（個別）」と「範囲エントリ（共通）」の2件の revision を持つ。
同じ日付・同じ diff_id の重複になるので、**(date, diff_id) で畳んで
individual 側を優先**する（個別エントリのほうが `lines_before` を持っている）。

### 2.4 `lawtext.py` への移動

`diff.py` から `find_articles` / `article_to_lines` / `format_paragraph` /
`format_item` / `index_by_num` を `lawtext.py` へ移し、`diff.py` は import する。
**振る舞いは変えない。** 既存の `tests/test_diff_*.py` が緑のままであることが
この移動の受け入れ条件。

## 3. 鮮度の保証（brief §5・§6・§8-4）

`law_summary.py` が採っている4点をそのまま移植する。発明しない。

1. `today = datetime.datetime.now(JST).date().isoformat()` を取り、
   `fetch_law_data(law_id, today)` を**生成と同じ実行のなかで**呼ぶ。
   `data/raw` は読まない。
2. 取得に失敗したら raise。古いファイルへ fallback しない。
3. 保存の直前に JST の日付を取り直し、`today` と違えば保存せず非ゼロ終了。
4. **`fetched_at`（秒精度の JST タイムスタンプ）を生成物に書く。**

4 がこの設計の中心。brief §6 の根っこは
「ディスク上のファイルは *いつ取得したか* を記録していない」だった。
**記録が無いのが問題なら、記録を作るのが答え。**
`asof` は「いつの法令か」、`fetched_at` は「いつ取ったか」で、別のキーに分けて両方持つ。

そのうえで **ページは「現在の条文」と言い切らず、取得日を併記する**:
「現在の条文（2026年9月22日時点）」。静的サイトである以上、生成後の改正は
原理的に反映できない。言い切ると嘘になる日が必ず来るので、言い切らない。
これは brief §3 の表現を弱める提案にあたる（そう明示しておく）。

### 検証（受け入れ基準4の具体形）

`tests/test_shipped_data.py` に足す。ファイル内で完結する検査だけを使う
（他のファイルの鮮度に依存すると brief §6-1 の①をもう一度踏む）:

- 全 `articles/*.json` に `fetched_at` があり、JST オフセット付きの ISO8601 として parse できる。
- **どの条文の `revisions[*].date` も `fetched_at` の日付以下**。
  超えていれば「取得より後に施行された改正を知っている」= 条文テキストが古い。
- `status == "current"` なら `current_lines` が空でない。
- `status == "deleted"` なら `former_lines` が空でなく、`deleted_on` がある。
- `slug` が `^[0-9]+(-[0-9]+)*$` に一致し、`:` を含まない（範囲がページ化されていない）。
- `articles` の `slug` が重複しない。

## 4. URL と条番号（brief §9-5）

- URL: `/law/<lawId>/article/<slug>`
- `slug` は `article_num` から: 数字はそのまま、`_` → `-`。
  `308_2` → `308-2`（第308条の2）、`117_2_2` → `117-2-2`。
  アンダースコアではなくハイフンにするのは、URL でアンダースコアが
  語の連結として扱われるため（検索エンジンの一般則）。
- 範囲形は slug を持たない（§2.3 で展開済み）。
- 変換は純粋関数として **Python 側 `article_slug()` と TS 側 `articleSlug()` の2箇所**に置く。
  生成物に `slug` を焼き込むので、TS 側は cross_reference の解決にのみ使う。
  **両者が一致することをテストで固定する**（Python のテストが slug 一覧を吐き、
  出荷データの slug と突き合わせる）。
- 日本語の条番号（`第三百六条`）は URL に使わない。パーセントエンコードで
  読めない URL になり、既存の `/diff/<diffId>` も ASCII で揃っている。
  日本語表記は `heading` として本文に出す。

## 5. フロント側

新規:

- `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx`
  - `generateStaticParams()` → 全法令の `{lawId, articleSlug}` 164 件
  - `generateMetadata()`:
    - title: `民法 第306条（一般の先取特権）｜2026年4月改正 - lexdiff`
      削除条文は `民法 第754条（削除）｜2026年4月1日に削除 - lexdiff`
    - description: 現行条文の先頭 + 最新改正の一行。削除条文は削除の事実を先頭に置く
    - canonical: `/law/<lawId>/article/<slug>`
  - `BreadcrumbJsonLd`: lexdiff › 法令名 › 第306条
- `frontend/components/article-text.tsx` — `current_lines` / `former_lines` の描画
- `frontend/components/article-revisions.tsx` — 改正履歴（降順）と `/diff` への導線

変更:

- `frontend/lib/data.ts` に `getArticlePageIds()` / `getArticlePages(lawId)` /
  `getArticlePage(lawId, slug)` を足す。`public/data/` を読む唯一の場所という
  現状の性質を壊さない。
- `frontend/lib/types.ts` に `ArticlePage` / `ArticleRevision` / `LawArticles` を足す。
- `frontend/app/law/[lawId]/page.tsx` に「改正された条文」一覧を足し、各条文ページへリンクする。
  **これが条文ページへの唯一の内部導線**になるので、ここを省くと 164 ページが孤立する。
- `frontend/app/diff/[diffId]/page.tsx` の各条文見出しから、対応する条文ページへリンクする。

## 6. `/diff` との重複（brief §9-4）

- canonical は互いに自分自身。統合しない。**単位が違う**
  （`/diff` = 改正1本で変わった全条文、`/article` = 条文1本の全履歴）。
- 重なるのは条文テキストだけで、`/diff` は改正前後の並置、`/article` は現行条文＋履歴。
  同一内容ではない。
- 内部リンクは双方向。`/article` → `/diff#<article_num>`、`/diff` の各条文 → `/article`。
- **`/diff` のページ構成は変えない。** 今そこに付いている順位を壊す変更をしない。

## 7. テスト（brief §8）

新規 `tests/test_article_pages.py`。既存の `tests/` の書き方（純粋関数を直接呼ぶ）に合わせる。

| テスト | 実装前 | 何を守るか |
|---|---|---|
| `test_fetch_failure_raises` | 赤 | 取得失敗時に raise し、何も保存しない（基準2） |
| `test_jst_date_change_refuses_save` | 赤 | 生成中に日付が変わったら保存しない |
| `test_range_article_expands_to_members` | 赤 | `753:754` が 753 と 754 に展開され、`753:754` のページは作られない |
| `test_duplicate_revision_folded` | 赤 | 同じ (date, diff_id) の個別+範囲が畳まれ、個別が残る |
| `test_deleted_article_keeps_former_text` | 赤 | 削除条文が `former_lines` と `deleted_on` を持つ |
| `test_article_slug` | 赤 | `306`→`306`、`308_2`→`308-2`、範囲は slug を持たない |
| `test_multi_revision_sorted_desc` | 赤 | `117_2_2` が2件を降順で持つ |
| `test_suppl_excluded` | 赤 | 附則がページにならない |

`tests/test_shipped_data.py` に §3 の検査を追加（出荷データ全件に対して走る）。

受け入れコマンド:

```
uv run pytest
cd frontend && npm run build && npm run lint
```

`npm run build` が 164 ページを静的生成することを、ビルド出力の件数で確認する。

## 8. この設計の弱いところ

1. **`fetched_at` は「取得の瞬間」を記録するが、「その後改正が無い」ことは保証しない。**
   静的サイトなので原理的に保証できない。だから「現在の条文」と言い切らず
   取得日を併記する、という逃げ方をしている。これは brief §3 の表現を弱めており、
   「現在の条文が読める」という当初の目的をわずかに下回る。
   再生成の頻度を運用で決める必要があるが、本設計はそこに触れていない。
2. **`diff.py` から `lawtext.py` への関数移動は、この機能に必須ではない。**
   import するだけでも動く。移動は「4つ目のコピーを作らない」ための予防であって、
   今回の目的には直接効かない差分を増やしている。既存テストが守っているとはいえ、
   条文ページのバグと移動のバグが同じ PR に混ざる。分けるべきかもしれない。
3. **164ページの内部リンクが `/law/<lawId>` 1枚に集中する。**
   民法なら1ページから39本。リンクの価値が薄く配られ、どの条文ページも弱いまま
   終わる可能性がある。章節でグルーピングする等の案はあるが、
   効果を測る手段が無いまま構造を複雑にすることになるので本設計では採っていない。
