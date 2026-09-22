# 条文ページ（issue #4）— 設計案 B

brief §3（1条文=1ページ / `/law/<lawId>/article/<条番号>` / 一括投入）を動かさない前提で、
**どう作るか**を書く。§9 の 6 論点には §7 で全部答える。

実データと実 API を開いて確認した。**brief の記述と食い違う事実が 3 つある**ので先に出す
（§0）。推測で書いた箇所は「未確認」と明記した。

---

## 0. 先に: brief の事実誤りと、確認できた新事実

### 0-1. 「民法第306条は 2024 と 2026 の両方に出る」は誤り（brief §9-3）

出荷済み 2 ファイルの本則 `article_num` を全部並べた（実測）:

```
129AC0000000089_2024-03-31_2024-04-01: 733 740 743 744 746 772 773 774 775 776 777 778 783 786 778_2 778_3 778_4
129AC0000000089_2026-03-31_2026-04-01: 306 749 753 754 765 766 768 770 788 797 811 818 819 833 308_2 766_2 766_3 824_2 824_3 817_12 817_13 753:754
```

306 は 2026 側にしか無い。**出荷済みデータ全体で、複数の diff にまたがる本則条文は
1 本だけ**である:

- 道路交通法 `117_2_2`（第百十七条の二の二）— `335AC0000000105_2024-10-31_2024-11-01`
  と `335AC0000000105_2026-03-31_2026-04-01` の両方に `modified` で出る。

本則エントリ 165 件 / ユニーク条文 164 件の差（=1）はこの 1 本である。
つまり §9-3 は「よくある形」ではなく **n=1 の形**。設計は必要だが、ここに凝る理由は無い。

### 0-2. `753:754` という `article_num` が実在する（URL 設計の本丸）

民法 2026 改正の本則エントリに、コロンを含む `article_num` が 1 件ある:

| article_num | type | title_before | title_after |
|---|---|---|---|
| `753` | deleted | 第七百五十三条 | null |
| `754` | deleted | 第七百五十四条 | null |
| `753:754` | added | null | 第七百五十三条及び第七百五十四条 |

これは e-Gov 側の `<Article Num="753:754">` をそのまま持ってきたもので、本文は「削除」の 1 行。
**今日の民法本文にも `Num="753:754"` が存在し、`753` と `754` は存在しない**（実測。
`asof=2026-09-22` で取得した本文の Article Num 一覧は `... 750 751 752 753:754 755 ...`）。

### 0-3. e-Gov API に条文単位の取得がある（brief §7 の「未検証」を潰した）

```
GET /api/2/law_data/{law_id}?asof=YYYY-MM-DD&elm=Article_306   → 200, 2,725 bytes
GET .../law_data/129AC0000000089?asof=...&elm=Article_308_2    → 200, 3,241 bytes
GET .../law_data/129AC0000000089?asof=...&elm=Article_753:754  → 200, 1,375 bytes
GET .../law_data/129AC0000000089?asof=...&elm=Article_753      → 400 {"code":"400021",
      "message":"要素（elm）に合致する要素が法令本文に存在しません。"}
```

レスポンスは全文取得と同じ 4 キー（`attached_files_info` / `law_info` / `revision_info` /
`law_full_text`）で、`law_full_text` が Article ノード 1 個になる。`revision_info` も付く。

**それでも採用しない。** 理由は 3 つ:

1. 163 リクエストに分けると、**取得の瞬間が 163 個に散る**。1 本の法令の条文ページ群が
   別々の改正時点の本文を持ちうる状態を自分で作ることになる。全文 1 回なら、その法令の
   全ページが 1 個の `law_revision_id` を共有する（鮮度の検証がここに乗る。§4）。
2. 12 → 163 で、途中失敗時の部分状態が生まれる。全文 1 回なら失敗は法令単位で原子的。
3. `fetch_law_data` をそのまま使える（brief §7「新しい取得器は書かない」）。`elm` は
   新しい引数を足す＝新しい取得経路を足すことになる。

コストは民法全文で 1.6MB / 1 リクエスト。11 法令で十数 MB。惜しむ額ではない。
`elm` は **人間が 1 条文を目視確認するときの道具**として docstring に残す（採用しない理由も）。

### 0-4. GSC で見えている 2 クエリは、両方とも今回の対象に入る

brief §1 が挙げる可視クエリ 2 件を出荷データと突き合わせた:

- 「e-gov 民法 第754条 夫婦間の契約の取消権」→ `754` は **`type: "deleted"`**。
- 「e-gov 民法 770条 離婚 2026」→ `770` は 2026 diff の `modified`。

**唯一まともに見えている 2 件のうち 1 件が削除条文である。** §9-6（deleted をページ化するか）
は、仮説検証そのものに直結する。作らない選択は、見えている証拠の半分を捨てる。

---

## 1. 方針（一段落）

新スクリプト `scripts/articles.py` を 1 本足す。既存の出荷済み diff JSON を読んで
「どの条文が、どの改正で、どう変わったか」を組み上げ、**その同じ実行のなかで e-Gov から
法令全文を 1 回取得**して現在の条文を差し込み、`frontend/public/data/articles/<lawId>.json`
に 11 ファイル書く。LLM は呼ばない。フロントは `/law/[lawId]/article/[articleSlug]` を 1 本
追加し、`data.ts` に読み出し関数を足すだけ。**slug も「ページがあるか」も Python 側で確定して
JSON に書く**ので、TypeScript 側に条番号のパース処理は 1 行も無い。

---

## 2. データ生成側

### 2-1. ファイルとコマンド

- 新規: `scripts/articles.py`
- 変更: なし（`fetch.py` / `lawtext.py` / `diff.py` は読むだけ。import して使う）
- 追加: `tests/test_articles.py`、`tests/test_shipped_data.py` に節を追加

```bash
uv run python scripts/articles.py 129AC0000000089   # 1法令
uv run python scripts/articles.py --all             # 出荷済み diff を持つ全法令
```

`--all` は `frontend/public/data/*_*-*-*_*-*-*.json` から law_id を集める（`tests/test_shipped_data.py`
の `shipped_diffs()` と同じ glob）。法令ごとに独立に fetch → 検証 → 保存し、1 法令が落ちても
他は保存する（法令単位で原子的）。最後に失敗した law_id を並べて非ゼロ終了。

### 2-2. 関数の責務分割（全部ピュア + main だけが IO）

| 関数 | 責務 | ピュア |
|---|---|---|
| `article_slug(article_num) -> str` | `"308_2"` → `"308-2"`。コロンを含む番号は `ValueError` | ○ |
| `display_num(article_num) -> str` | `"308_2"` → `"第308条の2"`、`"117_2_2"` → `"第117条の2の2"` | ○ |
| `merged_range_members(num) -> list[str]` | `"753:754"` → `["753","754"]`。端点が純数字でなければ `ValueError` | ○ |
| `collect_changes(diff_docs) -> dict[str, list[dict]]` | 本則エントリだけを `article_num` で束ね、施行日の新しい順に並べる。`753:754` は展開して `753` と `754` に配る（§7-6） | ○ |
| `index_articles(law_full_text) -> dict[str, dict]` | 今日の本文から `Num -> Article ノード`。`walk_tags(tree, {"Article"}, stop_at={"SupplProvision"})` をそのまま使う | ○ |
| `resolve_current(index, article_num) -> dict` | 現在の条文の解決。`present` / `merged` / `absent` を返す（§7-6） | ○ |
| `article_body(node) -> dict` | Article ノード → `{label, caption, paragraphs:[{num,text}]}`。`diff.format_paragraph` を再利用 | ○ |
| `build_law_articles(law_id, law_title, timeline, diff_docs, index, source) -> dict` | 出力 JSON の組み立て | ○ |
| `validate_articles(doc) -> list[str]` | 保存前検査（§2-5） | ○ |
| `fetch_current_text(law_id, today) -> tuple[dict, dict]` | `fetch_law_data` を呼び、`(index, source)` を返す。失敗は raise | × |
| `main()` | JST の today 決定 → fetch → build → validate → 日付再確認 → 原子的保存 → frontend へミラー | × |

既存の再利用（brief §7 の「再実装しない」に対応）:

- `fetch.fetch_law_data(law_id, asof)` — そのまま。新しい取得器は書かない。
- `lawtext.walk_tags` / `lawtext.extract_text` — 木の走査はこれだけ。新しい走査は書かない。
- `diff.format_paragraph` — 項の整形。diff 側と同じ見た目で条文を出すため、コピーしない。
  （`diff.py` は `httpx` を import しないピュアな読み込みが可能。未確認: import 時副作用は
  `main()` ガード下なので無い、と読んだ。実装時に `uv run python -c "import diff"` で確かめる。）
- `law_summary.fetch_evidence` / `main()` の 4 点（同一実行で取得 / 失敗は raise / JST の today /
  生成中に日付が変わったら保存しない）は **移植**。同じ形・同じ語彙で書く。

### 2-3. 出力先

```
frontend/public/data/
├── <lawId>_<before>_<after>.json     既存（変更しない）
├── timelines/<lawId>.json            既存（変更しない）
└── articles/<lawId>.json             ← 新規・11ファイル
```

- `data/articles/<lawId>.json` に書き、`frontend/public/data/articles/<lawId>.json`
  に **常に** 書く（既存ミラーの「宛先が既にあるときだけ」ではない。初回は宛先が無いので
  その規則だと 1 バイトも出荷されない）。`.gitignore` の `data/` 配下は既存どおり無視、
  `frontend/public/data/articles/` はコミットする。
- **なぜ 1 法令 1 ファイルか**: 163 個の小ファイルにすると `source`（取得日・リビジョン）が
  163 個に増え、「同じ法令のページが同じ取得に由来する」ことを検証するのに 163 個の突き合わせが
  要る。法令単位なら `source` は 1 個で、検証は「このファイルの全条文が同じ取得由来」に自明化する。
  最大は民法（39 条文、本文＋注釈＋diff 抜粋）で数百 KB。SSG のビルド時読み込みなので問題ない。
  （未確認: 実サイズは生成するまで出ない。100KB〜400KB と見積もった。）
- `data.ts::getDiffIds()` は `DATA_DIR` 直下の `.json` を拾うので、サブディレクトリ
  `articles/` は `f.endsWith(".json")` で落ちる。**既存の挙動に触らない。**

### 2-4. 出力 JSON の形（実キー名・実値）

```json
{
  "law_id": "129AC0000000089",
  "law_title": "民法",
  "source": {
    "asof": "2026-09-22",
    "fetched_at": "2026-09-22T14:07:31+09:00",
    "law_revision_id": "129AC0000000089_20260624_508AC0000000045",
    "amendment_enforcement_date": "2026-06-24",
    "amendment_law_title": "民法等の一部を改正する法律",
    "endpoint": "https://laws.e-gov.go.jp/api/2/law_data/129AC0000000089?asof=2026-09-22"
  },
  "articles": [
    {
      "article_num": "306",
      "slug": "306",
      "display_num": "第306条",
      "label": "第三百六条",
      "caption": "一般の先取特権",
      "section_path": ["第二編　物権", "第八章　先取特権", "第二節　先取特権の種類", "第一款　一般の先取特権"],
      "current": {
        "status": "present",
        "source_article_num": "306",
        "paragraphs": [
          {"num": "1", "text": "次に掲げる原因によって生じた債権を有する者は、債務者の総財産について先取特権を有する。\n　一\n　共益の費用\n　二\n　雇用関係\n　三\n　子の監護の費用\n　四\n　葬式の費用\n　五\n　日用品の供給"}
        ]
      },
      "plain_summary": "特定の種類の債権を持つ人が、債務者の全財産から優先的に支払いを受けられる権利（一般の先取特権）が発生する原因を列挙した条文",
      "cross_references": [
        {"ref": "第三百八条の二", "article_num": "308_2", "slug": "308-2", "has_page": true,
         "context": "子の監護の費用の先取特権が具体的にどの範囲の定期金債権に及ぶかを定めた条文"},
        {"ref": "第七百六十六条", "article_num": "766", "slug": "766", "has_page": true,
         "context": "離婚時に子の監護（養育費を含む）について父母が取り決めるべき事項を定めた条文"}
      ],
      "changes": [
        {
          "diff_id": "129AC0000000089_2026-03-31_2026-04-01",
          "enforcement_date": "2026-04-01",
          "year": "2026",
          "type": "modified",
          "amendment_law_title": "民法等の一部を改正する法律",
          "change_description": "これまでは「共益の費用」…新たに「子の監護の費用」が3番目の項目として追加され、5種類になりました。…",
          "diff": ["--- 旧 第三百六条", "+++ 新 第三百六条", "@@ -5,6 +5,8 @@", " 　二", " 　雇用関係", " 　三", "+　子の監護の費用", "+　四", " 　葬式の費用", "-　四", "+　五", " 　日用品の供給"],
          "entry_article_num": "306"
        }
      ]
    },
    {
      "article_num": "754",
      "slug": "754",
      "display_num": "第754条",
      "label": "第七百五十四条",
      "caption": "",
      "section_path": ["第四編　親族", "第二章　婚姻", "第二節　婚姻の効力"],
      "current": {
        "status": "merged",
        "source_article_num": "753:754",
        "source_label": "第七百五十三条及び第七百五十四条",
        "paragraphs": [{"num": "1", "text": "削除"}]
      },
      "former": {
        "as_of": "2026-03-31",
        "label": "第七百五十四条",
        "paragraphs": [{"num": "1", "text": "夫婦間でした契約は、婚姻中、いつでも、夫婦の一方からこれを取り消すことができる。ただし、第三者の権利を害することはできない。"}]
      },
      "plain_summary": "夫婦が結婚している間に交わした約束（契約）を、あとから一方的に取り消すことができるというルール",
      "cross_references": [],
      "changes": [
        {"diff_id": "129AC0000000089_2026-03-31_2026-04-01", "enforcement_date": "2026-04-01",
         "year": "2026", "type": "deleted", "amendment_law_title": "民法等の一部を改正する法律",
         "change_description": "これまでは、夫婦間で結んだ契約は婚姻中であればいつでも…この規定が削除されました。…",
         "diff": ["-第七百五十四条", "-夫婦間でした契約は、婚姻中、…"], "entry_article_num": "754"},
        {"diff_id": "129AC0000000089_2026-03-31_2026-04-01", "enforcement_date": "2026-04-01",
         "year": "2026", "type": "added", "amendment_law_title": "民法等の一部を改正する法律",
         "change_description": "改正前は第七百五十三条は既に廃止されていた欠番でしたが…",
         "diff": ["+第七百五十三条及び第七百五十四条", "+削除"], "entry_article_num": "753:754"}
      ]
    }
  ]
}
```

決めごと:

- `article_num` は diff JSON の値をそのまま持つ（照合の鍵）。`slug` は URL の値。
  **両方持つ**ので、フロントは変換しない。
- `label`（漢数字の条名）は今日の本文の `ArticleTitle` から取る。取れないとき（`merged`）は
  diff の `title_before` にフォールバック。`caption` は今日の本文の `ArticleCaption` から
  括弧を外したもの。**diff JSON には caption が入っていない**（`title_after` は「第三百六条」
  だけ）ので、これは全文取得の副産物として得られる純増の情報。`<title>` に効く。
- `display_num` は `article_num` から機械的に作る。プロダクトの手書き文言ではない。
- `plain_summary` は **施行日が最新の change の annotation** から取る。古い改正の
  `plain_summary` は「その改正当時の条文」の説明であって、現在の条文の説明ではない。
  道交法 `117_2_2` で実際に 2 個から選ぶことになる（§0-1）。
- `changes` は `enforcement_date` の降順。同日なら `entry_article_num` 昇順（754 の例のように
  同じ改正が deleted と added の 2 エントリを生むケースの安定ソート）。
- `cross_references` の `has_page` / `slug` は Python が計算した**事実**。フロントは
  `has_page` が真のときだけ `<Link>` にする。文言側で判断させない。
- 附則は入れない（`is_suppl` を捨てる）。brief §4 の非目標どおり。

### 2-5. `validate_articles(doc)`（保存前に必ず通す）

戻り値は文字列リスト。空でなければ **何も保存せず** `sys.exit(2)`。

1. `source` の 5 キーが全部あり、`asof` が `fetched_at` の JST 日付と一致する。
2. `articles` が空でない。
3. 各条文: `slug` がユニーク・`^[0-9]+(-[0-9]+)*$` に一致・`article_num` から
   `article_slug()` で再導出して一致する。
4. 各条文: `current.paragraphs` が 1 個以上あり、**全テキストを連結して空白を除くと非空**
   （brief §8-3。空文字ページ 0 件はここで担保する。空の `<Sentence/>` は
   `law_summary.build_evidence` が踏んだ形と同じなので、タグの有無ではなく中身で見る）。
5. 各条文: `changes` が 1 個以上あり、各 change に `change_description` が非空。
6. 各条文: `current.status` が `present` か `merged`。`absent` は **ここまで来ない**
   （§7-6 のとおり build 時に raise する）が、二重に落とす。
7. `source.amendment_enforcement_date <= source.asof`（未施行の本文が出荷されない）。

### 2-6. `main()` の順序（`law_summary.main()` の移植）

```
today = datetime.datetime.now(JST).date().isoformat()     # JST。施行日は日本の日付
index, source = fetch_current_text(law_id, today)          # 失敗は raise。古いファイルへ落ちない
doc = build_law_articles(...)                              # ここで absent なら raise
errors = validate_articles(doc)                            # 非空なら exit(2)、保存しない
if now(JST).date() != today: exit(3)                       # 生成中に日付が変わったら保存しない
write atomically (tmp -> os.replace) to data/ and frontend/public/data/articles/
```

`fetch_current_text` は `law_full_text` が無ければ `ValueError`。`httpx` の例外は
そのまま上げる（`law_summary` と同じ）。**フォールバックは一切書かない** — 古いファイルに
落ちることが brief §6-1 の事故そのものなので、落ちる先を作らない。

---

## 3. 条番号の URL 表現（§9-5）

### 実データの形（実測）

165 本則エントリの `article_num` を形で数えた:

| 形 | 件数 | 例 |
|---|---|---|
| `N` | 115 | `306` |
| `N_N` | 46 | `308_2`（第308条の2） |
| `N_N_N` | 3 | `117_2_2`（第117条の2の2）、`117_3_2` |
| `N:N` | 1 | `753:754` |

### 決定

- URL は **アラビア数字＋ハイフン**: `/law/129AC0000000089/article/306`、
  `/law/129AC0000000089/article/308-2`、`/law/335AC0000000105/article/117-2-2`。
- 変換規則は `_` → `-` の 1 対 1。`article_num` にハイフンは出現しない（上表）ので可逆。
- **コロンを含む番号は URL にしない**。`753:754` は `753` と `754` に展開する（§7-6）。
  `article_slug("753:754")` は `ValueError` を投げる。生成物にコロン slug は出ない。
- 日本語の条番号（`第308条の2`）は `display_num` として **本文・`<title>`・パンくず** に出す。
  URL には出さない。`/article/第308条の2` は percent-encoding で 30 文字を超え、共有時に壊れ、
  既存 `/diff/[diffId]` が `decodeURIComponent` を必要としている手間を 163 ページ分増やす。
- 漢数字（`第三百六条`）は `label` として現在の条文ブロックの見出しにだけ使う（e-Gov の原文表記）。

**なぜ `308_2` をそのまま URL にしないか**: アンダースコアは単語区切りとして扱われにくく、
`308_2` は検索エンジンにも人にも「308の2」と読ませにくい。`-` のほうが一般的で、
コストはゼロ。ただしこれは**好みの差の範囲**であり、「そのまま `308_2`」も許容できる。
議論を長引かせる価値は無い。決めの根拠は「変換が 1 対 1 で、Python が slug を JSON に
書き、TS が変換しない」のほうにある。

---

## 4. 鮮度の保証（§5・§6・§8-4）

### 4-1. どこに何を持つか

`source` ブロック（§2-4）を **法令ごとに 1 個**持つ。要点は 2 つ:

- `fetched_at` = **取得した瞬間**（JST、オフセット付き ISO8601）。
  `asof` = 取得に使った時点指定。この 2 つを別キーにするのが §6-1 の教訓の形。
  `asof` は「いつの法令か」、`fetched_at` は「いつ取ったか」。同じ実行で取るので
  `asof == fetched_at.date()` が不変条件になり、これが検証可能な形になる。
- `law_revision_id` = API が返した `revision_info.law_revision_id`
  （例 `129AC0000000089_20260624_508AC0000000045`）と
  `amendment_enforcement_date`（例 `2026-06-24`）。**取得した本文がどの改正の版か**を
  API 自身の言葉で記録する。実測: `asof=2026-09-22` の民法取得は
  `..._20260624_...` を返し、これは `law_revisions` 上で施行日 ≤ 今日の最大と一致した。

注意（実測）: `law_revisions` の `current_revision_status` は民法 37 版すべてが
`PreviousEnforced` か `UnEnforced` で、`CurrentEnforced` は 1 件も無い。
**このフィールドを「現行版か」の判定に使ってはいけない。** 使うのは `amendment_enforcement_date`。

### 4-2. どのテストがそれをどう読むか（全部オフライン）

`tests/test_shipped_data.py` に足す。CI はネットワークに出ない（`data/raw` は gitignore、
既存テストもすべてオフライン）ので、**出荷済みバイト列だけで判定できる形**にした。

| テスト | 読むもの | 落ちる条件 | 対応する受け入れ基準 |
|---|---|---|---|
| `test_shipped_article_files_are_present` | `articles/*.json` | 11 未満 | glob が空振りして以下が全部 vacuous になるのを防ぐ（既存 `test_shipped_diff_files_are_present` と同じ役割） |
| `test_shipped_articles_pass_validate_articles` | 各ファイル | `validate_articles(doc) != []` | §8-3（空文字ページ 0 件） |
| `test_shipped_article_source_is_one_run` | `source` | `asof != fetched_at` の日付 / `fetched_at` が tz-naive / オフセットが +09:00 でない | §8-4 の「取得日が記録されている」 |
| `test_shipped_article_text_is_not_older_than_known_enforcement` | `articles/<id>.source` と `timelines/<id>.json` | その法令の timeline にある施行日のうち `asof` 以下で最大のものが、`source.amendment_enforcement_date` より **新しい** | **§8-4 の本体** |
| `test_shipped_article_freshness_has_not_expired` | `source.fetched_at` | 今日 − `fetched_at` > 180 日 | 「現在の条文」という主張の賞味期限 |
| `test_shipped_articles_match_the_shipped_diffs` | `articles/*` と diff JSON | 生成側と同じピュア関数で diff から導いた条文集合と一致しない | §8-5 のページ数（マジックナンバーを使わない） |

`test_shipped_article_text_is_not_older_than_known_enforcement` が §6-1 の事故の形をそのまま
捕まえる: 刑法の全スナップショットが 2025-06-01 の拘禁刑統合より前だった、という状態は
「timeline が知っている施行日 2025-06-01 > 生成物が記録した取得版の施行日」として赤になる。
timeline 自体が古い可能性はあるが、**古い timeline は判定を緩めるだけで、誤って赤にはしない**
（下限としてしか使わないため）。これは意図した非対称。

`test_shipped_article_freshness_has_not_expired` は **意図的な時限装置**である。
半年後に誰も触らなくても CI が赤くなる。個人 OSS でこれは煩わしいが、ページの主張が
「現在の条文」である以上、放置が黙って進むほうが悪い。直し方は 1 行
（`uv run python scripts/articles.py --all` して commit）。
加えてページ本文にも「2026年9月22日時点」と明示するので、**期限切れでも嘘にはならない**
（時点付きの主張になる）。180 日という数字は ratchet であって物理量ではない。

### 4-3. 失敗時に何が起きるか

| 失敗 | 挙動 | 保存 |
|---|---|---|
| e-Gov が 5xx / タイムアウト | `httpx` 例外がそのまま上がる → 非ゼロ終了 | 何も書かない |
| `law_full_text` が無い | `ValueError` | 何も書かない |
| 施行済みなのに条文が本文に無い | `LookupError`（§7-6） | 何も書かない |
| `validate_articles` が非空 | メッセージを並べて `exit(2)` | 何も書かない |
| 生成中に JST 日付が変わった | メッセージを出して `exit(3)` | 何も書かない |
| `--all` で 1 法令だけ失敗 | その法令をスキップして続行、最後に一覧して非ゼロ終了 | 成功した法令だけ書く |

書き込みは `tmp` → `os.replace` の原子的置換。既存の良いファイルが壊れかけのもので
上書きされる経路を作らない（`law_summary.fetch_evidence` と同じ）。

---

## 5. フロント側

### 5-1. 新規ファイル

| パス | 中身 |
|---|---|
| `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx` | ページ本体・`generateStaticParams`・`generateMetadata` |
| `frontend/components/article-text.tsx` | 「現在の条文」ブロック（`current` + `former`） |
| `frontend/components/article-history.tsx` | 「この条文の改正履歴」ブロック（`changes` を新しい順に） |
| `frontend/components/article-links.tsx` | 「関連する条文」（`cross_references`） |

### 5-2. 変更するファイル

| パス | 変更 |
|---|---|
| `frontend/lib/types.ts` | 型を 6 個追加（§5-4） |
| `frontend/lib/data.ts` | 関数を 3 個追加（§5-3） |
| `frontend/app/sitemap.ts` | 条文ページを追加（`lastModified` = その条文の最新 `enforcement_date`、`priority: 0.7`） |
| `frontend/app/law/[lawId]/page.tsx` | 「この法令の改正された条文」一覧ブロックを追加（**163 ページを孤児にしないための内部リンク**。クロール経路はここだけ） |
| `frontend/components/diff-viewer.tsx` | 各条文エントリの見出しから `/law/<lawId>/article/<slug>` へリンク（`has_page` 相当の判定は生成物側の集合を見る。未確認: `DiffViewer` は現在 `lawId` を受け取っていないので props 追加が要る） |

### 5-3. `data.ts` に足す関数

```ts
const ARTICLE_DIR = path.join(DATA_DIR, "articles");

/** law ids that ship an articles file (11 of the 12 laws; 労働基準法 has no 本則 change). */
export function getArticleLawIds(): string[]

export function getArticleData(lawId: string): LawArticles

/** Every (lawId, articleSlug) pair that ships — what generateStaticParams returns. */
export function getArticleParams(): { lawId: string; articleSlug: string }[]

/** One article, or null. The page throws on null (a param came from this data). */
export function findArticle(lawId: string, slug: string): ArticlePage | null
```

`generateStaticParams` は `getArticleParams()` をそのまま返す。
`[{lawId: "129AC0000000089", articleSlug: "306"}, ..., {lawId: "335AC0000000105", articleSlug: "117-2-2"}]`
の 163 要素。**slug は JSON にあるものを読むだけで、TS は条番号を解釈しない。**

### 5-4. `types.ts` に足す型

```ts
export interface ArticleSource {
  asof: string;                       // "2026-09-22"
  fetched_at: string;                 // "2026-09-22T14:07:31+09:00"
  law_revision_id: string;
  amendment_enforcement_date: string;
  amendment_law_title: string;
  endpoint: string;
}

export interface CurrentText {
  status: "present" | "merged";
  source_article_num: string;
  source_label?: string;              // only when status === "merged"
  paragraphs: Paragraph[];            // existing Paragraph type, reused
}

export interface FormerText {
  as_of: string;
  label: string;
  paragraphs: Paragraph[];
}

export interface ArticleChange {
  diff_id: string;
  enforcement_date: string;
  year: string;
  type: "added" | "modified" | "deleted";
  amendment_law_title: string;
  change_description: string;
  diff: string[];
  entry_article_num: string;
}

export interface ArticleCrossReference extends CrossReference {  // existing CrossReference
  slug: string | null;
  has_page: boolean;
}

export interface ArticlePage {
  article_num: string;
  slug: string;
  display_num: string;                // "第308条の2"
  label: string;                      // "第三百八条の二"
  caption: string;                    // "子の監護費用の先取特権"
  section_path: string[];
  current: CurrentText;
  former?: FormerText;
  plain_summary: string;
  cross_references: ArticleCrossReference[];
  changes: ArticleChange[];
}

export interface LawArticles {
  law_id: string;
  law_title: string;
  source: ArticleSource;
  articles: ArticlePage[];
}
```

### 5-5. ページの構成（上から）

1. パンくず（`BreadcrumbJsonLd` を再利用）: lexdiff / 民法 / 第306条。`section_path` はその下に
   小さく（`第二編　物権 › 第八章　先取特権 › …`）。
2. **見出し**: `民法 第306条（一般の先取特権）`。
3. **現在の条文**（ページの主役。最上部）。ブロック見出しは
   `現在の条文（2026年9月22日時点）` — 日付は `source.asof` から。
   `status: "merged"` のときは見出しの下に 1 行:
   `第753条・第754条は「第七百五十三条及び第七百五十四条 削除」として欠番です（2026年9月22日時点）。`
   e-Gov 原文への外部リンク（既存 `/law` ページと同じ `laws.e-gov.go.jp/law/<lawId>`）。
4. **削除前の条文**（`former` があるとき）:
   `2026年4月1日改正で削除される前の条文` + 本文。これが 754 検索者への回答になる。
5. **この条文は何をする条文か**: `plain_summary`。
6. **この条文の改正履歴**: `changes` を新しい順にカード化。各カードは
   `2026年4月1日施行・民法等の一部を改正する法律` / `change_description` /
   折りたたんだ差分（`diff` の unified 行を既存 `diff-viewer` と同じ配色で） /
   `この改正の全体を見る →` で `/diff/<diff_id>` へ。
7. **関連する条文**: `has_page` が真なら `/law/<lawId>/article/<slug>`、偽なら
   `laws.e-gov.go.jp/law/<lawId>` への外部リンク。各行に `context` を添える。
8. フッタ: `<法令名>の改正履歴をすべて見る →` で `/law/<lawId>`。

**テンプレート文言に法的主張を書かない**（brief §5 / law-seo.ts の教訓）。
上の日本語で条件付きの法的内容を言っているのは 3 の「欠番です」だけで、これは条文本文
（「削除」）と `source_label` から機械的に導いた事実。要件・制裁・期限の類は 1 つも書かない。

### 5-6. metadata

```ts
export async function generateMetadata({ params }) {
  const { lawId, articleSlug } = await params;
  const data = getArticleData(lawId);
  const a = findArticle(lawId, articleSlug)!;
  const head = a.caption ? `${data.law_title}${a.display_num}（${a.caption}）` : `${data.law_title}${a.display_num}`;
  const years = [...new Set(a.changes.map((c) => c.year))].join("・");
  return {
    title: `${head}の条文と改正（${years}年改正）`,
    description:
      `${head}の現在の条文（${data.source.asof}時点）と、${years}年改正での変更点。` +
      `改正前後の条文、関連する条文へのリンクを掲載。`,
    alternates: { canonical: `/law/${lawId}/article/${articleSlug}` },
    openGraph: { title: `${head} | lexdiff`, description: a.plain_summary },
  };
}
```

`layout.tsx` の `title.template` が `%s | lexdiff` なので最終形は
`民法第306条（一般の先取特権）の条文と改正（2026年改正）| lexdiff`。

- `<title>` に入れる語は全部**計算値**（法令名・条番号・caption・年）。`law-seo.ts` のような
  手書きマップは **作らない**。作るなら GSC で「同じページが片方のクエリ形で勝って
  もう片方で負けている」が見えてから（`law-seo.ts` の docstring が定めた条件そのもの）。
- 可視クエリ 2 件は「e-gov 民法 第754条 夫婦間の契約の取消権」型。`caption` を
  タイトルに入れることが直接効く（`夫婦間の契約の取消権` は民法 754 の caption そのもの。
  **未確認**: 754 は現在欠番なので今日の本文から caption が取れない。`former` 側の
  caption は diff JSON に無い。→ §8 の弱点 3 に書いた）。

---

## 6. `/diff` との重複（§9-4）

- **canonical は自己参照**。`/diff/<id>` の canonical は現状どおり `/diff/<id>`、
  条文ページは `/law/<id>/article/<slug>`。**どちらも noindex にしない。**
  `/diff` はサイト最大の表示回数を持つ資産で、仮説が外れたときに残るのはこちら。
- 実際に重複するテキストはどれか、を数えると小さい。条文ページの本文は
  「今日の条文全文＋削除前条文」で、`/diff` に出るのは「unified diff の行」と
  `paragraphs_before/after`。最新改正で変わった条文は `paragraphs_after` ≒ 今日の条文なので
  そこは重なる。重ならないのは: caption、`plain_summary`、複数改正の束ね、
  `cross_references`、取得日時点の表示。
- Google に同一サイト内の重複ペナルティは無い。実際の risk は
  **同じクエリに対してどちらを出すか Google が選ぶ**こと。狙いを条文ページに寄せるため:
  - `/diff` の各条文見出し → 条文ページへのリンク（アンカーテキスト＝`第306条（一般の先取特権）`）
  - `/law` の条文一覧 → 条文ページ（クロール経路の本体）
  - sitemap で条文ページの `priority` を `/diff` と同じ 0.7 にする（priority に効果は
    ほぼ無いので、これは主張ではなく整合）
  - 条文ページ → `/diff` は「この改正の全体を見る」の 1 本だけ（逆流を細くする）
- **8 週後に、同じクエリで両方が出ているなら、それは仮説が当たった側の問題**であって、
  そのとき `/diff` 側に条文ページへの canonical を向けるかを判断する。今は判断しない。

---

## 7. 未決論点への回答（§9 の 6 つ）

### 7-1. n=4 の仮説で 163 ページを一括で作るのは妥当か

**結論: 作ってよい。ただし brief に無い 2 つを足すことを条件にする。**

まず、より安い検証手段を探した結果:

| 案 | 実際の安さ | 判定 |
|---|---|---|
| 5〜10 ページだけ作って 8 週待つ | 生成コストは 163 も 10 も同じ 1 コマンド。**安くならない** | × |
| 生成せず GSC をもっと掘る | 0 円で今日できる。ただし GSC の匿名化は解けない | **△ 並行してやる** |
| Bing Webmaster Tools を入れる | 0 円。Bing はクエリを匿名化しない。母数は小さいが**意図の分布**は見える | **○ 並行してやる** |
| `/diff` のタイトルに条番号を足して CTR を見る | 既存 358 imp に対する A/B。安いが、条文が無いままなので仮説の核心を検証しない | × |

**この仮説検証は「作る」以外に安い手が無い型である。** 理由は単純で、コストの大半は
生成ではなく設計・レビュー・保守であり、それはページ数に比例しない。10 ページでも同じ
スクリプト・同じテスト・同じフロントを書く。**ページ数を減らしても節約できるのは
「もし失敗だったときに消す手間」だけで、それは `git revert` 1 回。**

条件として足すもの:

1. **打ち切り基準を先に書く。** 8 週後（投入日 + 56 日）に GSC で `/law/*/article/*` を見て、
   **表示回数 200 未満なら noindex（削除ではなく）**、**表示回数 500 以上かつクリック 0 なら
   `/diff` と同じ病気なので設計から見直し**、**クリック 5 以上なら残す**。
   この 3 本を `docs/` に残してから出荷する。数字は今の `/diff` の 358 imp / 0 click と
   `/law` の 91 imp / 3 click を基準にした一桁の当て推量であり、根拠はその 2 行だけ。
   **当て推量であることを明記して置く**（あとから「根拠があった」と誤読されないため）。
2. **薄いページを作らない床を検査で持つ。** 「`current` が非空 かつ `plain_summary` が非空
   かつ `changes` が 1 件以上」を `validate_articles` で必須にする（§2-5）。163 件すべてが
   今日この床を満たす（出荷済み 165 エントリに annotation 欠損 0 件、実測）。床を割る条文が
   将来出たら、そのページは生成されずスクリプトが落ちる。**薄いページの量産は起こりえない**
   という状態を、意志ではなく検査で持つ。

仮説に対して brief が言っていない**反証の芽**も 1 つ置いておく:
可視 2 クエリはどちらも **「e-gov」を含む**。これは「e-Gov のあのページに行きたい」という
ナビゲーショナル寄りの意図であり、条文を載せてもクリックは e-Gov に行く可能性がある。
条文ページがこの意図に勝てるとしたら、勝ち筋は「条文＋いつどう変わったか」が 1 画面にあること
であって、条文そのものではない。**だから改正履歴ブロックを条文の直後に置く**（§5-5 の 6）。

### 7-2. 「現在の条文」をどう記録し、どう検証するか

§4 に全部書いた。要点だけ:
`source.fetched_at`（取得の瞬間）と `source.asof`（時点指定）を**別キーで**持ち、
同一実行で取るので `asof == fetched_at.date()` が不変条件になる。加えて API 自身が返した
`law_revision_id` と `amendment_enforcement_date` を持つ。検証は 6 本のオフラインテスト、
本体は「出荷済み timeline が知っている施行日（≤ asof の最大）より、生成物の版が古くないこと」。

### 7-3. 1 条文が複数の改正で変わっている場合の構成

実データでは **n=1**（道交法 `117_2_2`、2024-11-01 と 2026-04-01。§0-1）。

- 1 ページに `changes` を**施行日の新しい順**で縦に積む。タブにも折りたたみにもしない
  （2 件に UI を足すのは過剰）。
- ページ上部の `plain_summary` は**最新の change のもの**を使う。古い annotation は
  当時の条文の説明であり、現在の条文の説明として出すと §6-3（廃止刑名）と同じ型の誤りになる。
  古いほうの `plain_summary` は**捨てる**（履歴カードには `change_description` だけ載る）。
- 同じ改正が 1 条文に 2 エントリを生むケース（754 の deleted + 753:754 の added）も
  同じ `changes` 配列に並ぶ。`entry_article_num` を持たせて、どの diff エントリ由来かを
  ページ側で区別できるようにした。
- 「前回の改正で入った文言が今回また変わった」の連鎖を可視化する案は**やらない**。
  条文本文の系列復元になり、新しい取得（各改正時点の本文）が要る。brief §4 の範囲外。

### 7-4. `/diff` との重複

§6 に書いた。canonical は自己参照、noindex なし、内部リンクは `/law` と `/diff` から
条文ページへ太く、逆は細く。

### 7-5. 条番号の URL 表現

§3 に書いた。`_` → `-`、コロンは展開して消す、日本語は本文と `<title>` にだけ。

### 7-6. 削除された条文（§9-6）

**作る。** 理由は §0-4 — 見えている 2 クエリのうち 1 件が民法 754 である。
「削除されたと知りたい」は正当な検索意図であり、e-Gov で 754 を引くと
「第七百五十三条及び第七百五十四条 削除」としか出ない。**「いつ・なぜ消えたか」は
e-Gov が持っていない付加価値そのもの**（brief §2-2）。

解決規則 `resolve_current(index, article_num)`:

```
1. index に article_num が完全一致 → status "present"
2. index のキーのうち "A:B" 形のものを探し、A <= article_num <= B（純数字比較）なら
   → status "merged"、source_article_num = "A:B"、本文はそのノード（民法 753/754 → "削除"）
3. どちらでもない → LookupError を投げて main を落とす（後述）
```

3 に落ちる状況は 2 通りある:

- **施行済みの改正で追加/変更された条文が、今日の本文に無い** → 我々の法令構造の理解が
  間違っているか、e-Gov 側で構造が変わった。**黙って飛ばさず落とす。** 飛ばすと
  「163 ページのはずが 161 ページ」が誰にも見えないまま出荷される。
- **まだ施行されていない改正**（diff の `date_after` が未来）。出荷済み diff は全部
  過去日付だが、将来必ず起きる。→ `build_law_articles` は `date_after > today` の diff を
  **対象から外し**、スキップした diff_id と理由を stdout に出す。未施行の改正に
  「現在の条文」は存在しないので、ページを作らないのが正しい。

ページの見え方（754 の例）:

- 見出し `民法 第754条`
- 現在の条文: `第753条・第754条は「第七百五十三条及び第七百五十四条 削除」として欠番です
  （2026年9月22日時点）。`
- 削除前の条文: `2026年4月1日改正で削除される前の条文` +
  「夫婦間でした契約は、婚姻中、いつでも、…」
- 何をする条文だったか: `plain_summary`
- 改正履歴: 2026年4月1日施行の change カード

**ページ数は 164 → 163 になる。** `753:754` を独立したページにしないため。
これは brief §3 からの逸脱なので理由を書く: `753:754` は条番号ではなく e-Gov の要素 ID で、
誰も `753:754` を検索しない。中身は「削除」の 2 文字。`753` と `754` に畳めば、
**検索される番号は全部アドレス可能なまま**で、失われるページは「削除としか書いていない
1 ページ」だけ。受け入れ基準 5 の「164 ページ」は
**「生成物から導いた条文集合と同じ枚数がビルドされること」**に読み替える
（マジックナンバーを固定すると、法令を 1 本足した瞬間に意味を失う）。
その枚数は今日の出荷データで **163**。

---

## 8. テスト

既存の書き方に合わせる: `sys.path.insert(0, scripts)` してから import、合成木のフィクスチャ
（`data/raw` は gitignore なので実スナップショットを読まない）、`monkeypatch` で
`fetch_law_data` / `DATA_DIR` / `FRONTEND_DIR` / `sys.argv` を差し替え
（`tests/test_law_summary_validation.py::_run_main` と同じ形）。

### `tests/test_articles.py`（新規・ピュア関数と main の経路）

| # | テスト | いま | 実装後 | 受け入れ基準 |
|---|---|---|---|---|
| 1 | `test_slug_round_trip` — `306`/`308_2`/`117_2_2` が `306`/`308-2`/`117-2-2` になり戻る | 赤（関数が無い） | 緑 | §9-5 |
| 2 | `test_slug_rejects_a_range_num` — `article_slug("753:754")` が `ValueError` | 赤 | 緑 | §9-5 |
| 3 | `test_display_num` — `117_2_2` → `第117条の2の2` | 赤 | 緑 | — |
| 4 | `test_resolve_current_finds_an_exact_article` | 赤 | 緑 | §8-3 |
| 5 | `test_resolve_current_folds_a_merged_range` — index に `753:754` だけある木で `754` を引くと status `merged`・本文「削除」 | 赤 | 緑 | §9-6 |
| 6 | `test_resolve_current_raises_when_an_enforced_article_is_absent` — `LookupError` | 赤 | 緑 | §9-6 |
| 7 | `test_main_exits_nonzero_and_saves_nothing_when_the_fetch_fails` — `fetch_law_data` が `httpx.HTTPError` を投げる。`tmp_path` 配下に 1 ファイルも無いことを確認 | 赤 | 緑 | **§8-2（赤→緑を示す本体）** |
| 8 | `test_main_saves_nothing_when_the_api_returns_no_law_full_text` | 赤 | 緑 | §8-2 |
| 9 | `test_main_does_not_save_when_the_day_changes_mid_generation` — `Clock` で 2 回目の `now()` を +1 日（既存テストの写し）。`exit(3)`・保存 0 件 | 赤 | 緑 | §5 |
| 10 | `test_validate_rejects_an_empty_current_text` — 空 `<Sentence/>` だけの条文 | 赤 | 緑 | **§8-3** |
| 11 | `test_validate_rejects_a_duplicate_slug` | 赤 | 緑 | §8-5 |
| 12 | `test_changes_are_newest_first` | 赤 | 緑 | §9-3 |
| 13 | `test_plain_summary_comes_from_the_newest_change` — 2 改正の合成データで古いほうの文言が出ないこと | 赤 | 緑 | §9-3 |
| 14 | `test_cross_reference_has_page_is_false_for_an_unchanged_article` | 赤 | 緑 | §2-4 |
| 15 | `test_unenforced_diffs_are_skipped` — `date_after` が未来の diff が `changes` に入らない | 赤 | 緑 | §7-6 |
| 16 | `test_suppl_entries_never_become_pages` — `is_suppl` を持つエントリが 1 件も混じらない | 赤 | 緑 | §4 非目標 |

### `tests/test_shipped_data.py`（追記・出荷済みバイト列）

§4-2 の表の 6 本。いまは全部赤（`articles/` が存在しない）。生成後に緑。

### フロント側

repo に JS のテストランナーは無い（CI は `npm run lint` と `npm run build` のみ）。
**足さない。** 代わりに:

- 条番号の解釈を TS から消した（slug は JSON にある）ので、テストすべきロジックがほぼ無い。
- ビルド時アサーションを 1 本置く: `generateStaticParams` の中で、
  返す params がユニークであることと 1 件以上あることを確認し、違反したら `throw`
  （`assertLawSeoOverridesValid` と同じ「ビルドを落とすのが唯一の到達するフィードバック」の形）。

### 受け入れコマンド（そのまま走らせる）

```bash
uv run pytest                                             # §8-1
uv run python scripts/articles.py --all                   # 生成（e-Gov へ 11 リクエスト）
uv run pytest tests/test_shipped_data.py                  # §8-3 §8-4
cd frontend && npm run lint                               # §8-6
cd frontend && npm run build                              # §8-5
find frontend/out -path '*/article/*' -name '*.html' | wc -l   # → 163
python3 -c "import json,glob;print(sum(len(json.load(open(f))['articles']) for f in glob.glob('frontend/public/data/articles/*.json')))"  # → 163（上と一致）
```

---

## 9. この設計の弱いところ（自己申告・3つ）

### 弱点 1: 「最新施行版より古くない」の検証が、自分より古いかもしれないファイルを基準にしている

§4-2 の本体テストは、生成物の `amendment_enforcement_date` を **出荷済み timeline** の
施行日と比べる。ところが `timeline.py` は既存ファイルを無期限に再利用する（brief §6-1 の
①で名指しされている、まさにその性質）。timeline が古ければ、このテストは「古い下限」と
比べるだけになり、**本当に古い条文を通してしまう**。

つまりこのテストが捕まえられるのは「timeline は更新されたのに articles が更新されていない」
という**片方だけ古い**状態であって、「両方古い」は捕まえられない。両方古いケースを塞ぐのが
`test_shipped_article_freshness_has_not_expired`（180 日）だが、それは日数の当て推量である。

ネットワークに出るテスト（CI で `law_revisions` を引いて突き合わせる）なら塞げるが、
この repo のテストは全部オフラインで、e-Gov の可用性で CI が赤くなる形は入れたくなかった。
**妥協した箇所であり、そう明記する。** 代替案として「`scripts/articles.py --verify` という
ネットワークを使う別コマンドを置き、CI ではなく手元と週次で回す」を提案するが、
「回されない手順は無いのと同じ」なので、これが弱いことは変わらない。

### 弱点 2: 削除条文のページに caption が無い

`caption`（`（夫婦間の契約の取消権）`）は**今日の本文の `ArticleCaption`** から取っている。
754 は今日の本文に存在しない（`753:754` に畳まれ、そのノードに caption は無い）ので、
**754 のページの `<title>` には caption が入らない**。

ところが GSC で見えている唯一のクエリは
「e-gov 民法 第754条 **夫婦間の契約の取消権**」— **caption そのものを打っている**。
つまり、この設計はいちばん証拠のあるクエリに対して、いちばん効く語をタイトルに持てない。

diff JSON の `title_before` は「第七百五十四条」だけで caption を含まない（実測）ので、
出荷済みデータからは復元できない。復元するには改正前時点（`2026-03-31`）の本文をもう 1 回
取得する必要があり、それは「唯一の新規取得」を 2 種類に増やす。
**今回はやらない**（`plain_summary` が meta description と本文に出るので、語としては
ページ内に存在する。`<title>` に無いだけ）。ただし brief §1 の証拠の中心に対する取りこぼしで、
**弱点 1 より実害が早い可能性がある**。

### 弱点 3: 内部リンク経路が `/law` ページ 1 本に集中している

163 ページへのクロール経路は、実質 `/law/<lawId>` に足す条文一覧ブロックと sitemap だけ。
`/law` は 11 ページしかなく、そこから 163 ページがぶら下がる形は
**サイト構造として深く・薄い**。1 ページに 39 本のリンクが並ぶ法令（民法）もある。

より良い形は「章・節（`section_path`）でグルーピングした中間ページ」だが、それは
「薄いページを量産しない」という非目標に逆行する（中間ページ自体が薄い）。
`cross_references` による横方向のリンクはあるが、これは条文同士をまばらに繋ぐだけで、
到達性を保証しない（リンクされない条文が出る）。

結果として、**163 ページのうち一定数はインデックスされない可能性がある**。
それが起きたとき、8 週後の「表示回数 200 未満」は「仮説が外れた」ではなく
「クロールされなかった」を意味しうる。**打ち切り判断が汚染される。**
対策として `Search Console のインデックス作成レポートで「検出 - インデックス未登録」の
件数を先に見る` を 8 週後の手順に入れておくが、これは観測の追加であって、構造の解決ではない。
