# 条文ページ（issue #4）— 確定仕様 / Gate 1 出力

これは Gate 1（設計レビュー）の成果物。次の工程は Gate 2（plan の敵対レビュー）。

出典: `verdict.md`（裁定 = codex）の確定仕様を、親セッションが repo 実測で濾したもの。
ユーザー判断が裁定より優先する箇所は §0 に明記する。

---

## 0. 人が決めたこと（裁定より優先）

1. **作るもの**: 条文1本=1ページ、URL は `/law/<lawId>/article/<条番号>`、一括投入。
2. **現在の条文の鮮度**: 生成と同じ実行で e-Gov から取得。失敗したら止まる。
   ディスク上のファイルから鮮度を判定しない。
3. **本文と解説の版ズレ（§4）**: 照合して**不一致なら解説ブロックを落とす**。
   時点ラベルを付けて出す案は却下（著作権法122条の2のように条番号が別規定へ
   付け替わったケースでは、時点ラベルがあっても読者は「同じ条文の昔の説明」と誤読する）。

裁定はこの3点すべてと整合しており、矛盾は無い。

---

## 1. 対象と URL

- URL: `/law/<lawId>/article/<slug>`
- 対象は出荷済み diff のエントリのうち、次を全部満たすもの:
  - 本則である（`is_suppl` が偽）
  - `date_after <= 生成時の JST 日付`（未施行の改正は対象外）
  - `article_num` が単独条番号（範囲形 `A:B` ではない）
- 現在の出荷データでは **163 ページ**。
  **この件数をテストへ固定しない**（法令を1本足せば変わる値）。
  検査は「生成 JSON の slug 数 == 静的生成された HTML 数」。
- 本則対象が 0 件の法令（労働基準法）は**正常終了し、ファイルを作らない**。
- slug 変換は **Python だけ**で行う:
  - `306` → `306` / `308_2` → `308-2` / `117_2_2` → `117-2-2`
  - `:` を含む番号は slug 化を**拒否**（`ValueError`）
- 日本語表記は `display_num`（`第308条の2`）として生成し、本文・`<title>`・パンくずに使う。
- **TypeScript 側に条番号・slug の変換関数を作らない。** 生成物の `slug` を読むだけ。

---

## 2. 生成スクリプト

新規 `scripts/articles.py`。

```bash
uv run python scripts/articles.py <law_id>
uv run python scripts/articles.py --all
```

| 関数 | 責務 |
|---|---|
| `collect_changes()` | 出荷済み diff から対象条文と改正履歴を集める |
| `article_slug()` | 単独条番号 → slug。範囲形は拒否 |
| `index_current_articles()` | `walk_tags(..., {"Article"}, stop_at={"SupplProvision"})` で現行本則を索引化 |
| `extract_article_body()` | `ArticleTitle` / `ArticleCaption` / `Paragraph` を**分離して**取り出す |
| `resolve_current()` | `present` / `merged_deleted` / エラー を判定 |
| `texts_match()` | 最新 diff 直後の本文と現在本文の版整合を判定 |
| `resolve_cross_references()` | 同法令内の安全なリンクだけを確定 |
| `build_law_articles()` | 法令単位 JSON を構築 |
| `validate_articles()` | 保存前検証 |
| `main()` | 取得 → 構築 → 検証 → 日付再確認 → 保存 |

**再利用する（再実装しない）**: `fetch.fetch_law_data(law_id, asof)` /
`lawtext.walk_tags` / `lawtext.extract_text` / 既存の段落・Item 整形処理。

**`extract_article_body()` を新規に書く理由**: `diff.py` の `find_articles` は
`ArticleCaption` を読んだ後 `ArticleTitle` で上書きするため caption が消える（R1 で実測）。
これは既存のバグだが、**本仕様では直さない**。`diff.py` へ触らず、条文ページ側で
`ArticleTitle` と `ArticleCaption` を別々に読む。caption バグは別 issue。

**`diff.py` から `lawtext.py` への関数移動はやらない。** 本機能の必須条件ではなく、
移動のバグと条文ページのバグが同じ差分に混ざる。

**e-Gov の `elm` による条文単位取得は採用しない。** 実在する（実測: `Article_306` → 200 /
`Article_754` → 400021）が、1法令1レスポンス・1 revision で全対象条文が取れるほうが
provenance が1つに揃い、既存取得器を変更しなくて済む。

---

## 3. 取得と保存の原子性

1. JST の `today` と開始時刻を取得
2. 法令ごとに `fetch_law_data(law_id, today)` を **1回**呼ぶ
3. `law_full_text` と `revision_info` が無ければ失敗
4. 全法令ぶんをメモリ／一時領域で生成・検証する
5. 保存直前に JST 日付を再確認
6. 変わっていたら**何も公開せず**非ゼロ終了
7. 全対象法令が成功した後だけ、一時ファイルから原子的に置換

`--all` で1法令でも失敗したら、**今回生成したファイルを一つも公開しない**。
途中まで成功した法令だけ更新する方式は採らない。

出力先:
- `data/articles/<lawId>.json`
- `frontend/public/data/articles/<lawId>.json`（コミット対象）

**`.gitignore` に `data/articles/` を追加する。** 現在の `.gitignore` は列挙式で
`data/raw/` `data/diffs/` `data/timelines/` `data/proposers/` のみ。
CLAUDE.md の「`data/` … all subdirs gitignored」も併せて直す。

---

## 4. 本文と annotation の版整合ゲート（出荷必須条件）

**これが本仕様の中心。** 対象条文の最新の**個別** diff エントリについて、
`paragraphs_after` と今日取得した本文を比較する。比較対象は段落番号と本文。
改行コード・末尾空白以外は正規化しない。

### 一致する場合

- `annotation.plain_summary` を `current_summary` として表示してよい
- 最新 annotation の cross references を「関連する条文」の候補にできる
- `current_summary.evidence_date` を記録する
- **例外**: 現行本文に存在しない廃止刑名（懲役 / 禁錮 / 禁固 / 禁こ）が summary に
  含まれる場合は一致扱いにせず、現在の説明から除外する

### 一致しない場合

- `plain_summary` を「この条文は何をする条文か」として**表示してはならない**
- `current_summary` は `null`
- ページには機械的な案内を出す:
  「現行本文に対応する解説は未収録です。収録済み改正時点の説明は改正履歴で確認できます。」
- `plain_summary` は対応する**履歴カード内へ移し**、
  「YYYY年M月D日改正直後の条文についての説明」と時点を明示する
- cross references も現在の関連条文とはせず、同じ履歴カード内で時点付き表示にする

`change_description` は**改正履歴の中だけ**で使用し、必ず施行日・改正法名と同じカードに置く。
これにより「懲役」などの歴史的表現が現行制度の説明として読まれないようにする。

**この規則が要る理由（実測）**: 出荷済み diff は実際の法令から5〜24か月遅れており、
12法令すべてでズレている。162条文中30条文で本文が変わっている。
刑法183条は本文「三年以下の拘禁刑」／解説「3年以下の懲役」、
著作権法122条の2は本文「帳簿を備えず…罰金」／解説「秘密保持命令違反の刑罰」で、
後者は古いのではなく**別の条文の説明**。

---

## 5. 出力データ

```json
{
  "law_id": "129AC0000000089",
  "law_title": "民法",
  "source": {
    "asof": "2026-09-22",
    "fetched_at": "2026-09-22T14:07:31+09:00",
    "law_revision_id": "129AC0000000089_20260624_508AC0000000045",
    "amendment_enforcement_date": "2026-06-24"
  },
  "articles": [ /* 条文レコード */ ]
}
```

条文レコード:

```json
{
  "article_num": "306",
  "slug": "306",
  "display_num": "第306条",
  "label": "第三百六条",
  "caption": "一般の先取特権",
  "section_path": ["第二編　物権", "第八章　先取特権", "..."],
  "current": { "status": "present", "source_article_num": "306", "paragraphs": [] },
  "current_summary": { "text": "...", "evidence_date": "2026-04-01" },
  "former": null,
  "changes": [],
  "related_articles": []
}
```

決めごと:

- `label`（漢数字）と `caption` は**今日取得した Article ノードから直接、別々に**読む
- `section_path` は最新の個別 diff エントリから取る
- `changes` は施行日の降順。複数改正を持つ道交法 `117_2_2` も同じ配列で扱う
- `former` は個別エントリが `deleted` のときだけ、その `paragraphs_before` と
  `date_before` から作る。見出しは「**今回の改正直前の条文**」とし、
  法律制定時の元条文であるかのように表示しない
- diff の範囲エントリは `changes` へ**入れない**

---

## 6. 範囲ノードと削除条文

`753:754` のような範囲形は**ページを持たない**。

### diff 側の範囲エントリ

- 同じ diff・同じ施行日に各構成員の個別エントリが存在する場合、
  範囲エントリはページ生成の入力から**除外する**
- 個別エントリのない範囲エントリを検出したら、**自動展開せず生成を失敗させる**

（理由: `753:754` の `plain_summary` は 754 の内容しか書いていない。
753 へ配ると「第753条は夫婦間契約取消権に関するルール」という誤りになる。実測で確認済み。）

### 現行法側の範囲ノード

`resolve_current()` の解決順:

1. `article_num` 完全一致 → `present`
2. 対象が個別 diff 上で `deleted` であり、範囲ノードがその番号を含み、
   **かつノード本文が実質的に「削除」だけ** → `merged_deleted`
3. それ以外 → `LookupError`（生成を落とす）

育児介護休業法の `36:52`（17条ぶんを覆う）のような広い範囲へ番号が入るだけでは
削除済みと判定しない。

### 削除条文ページの表示順

1. **現在の姿**: 「第753条・第754条は『第七百五十三条及び第七百五十四条　削除』として
   扱われています（取得日時点）」
2. **今回の改正直前の条文**: 日付と「現行法ではありません」を明示
3. 改正履歴と既存 annotation
4. `/diff` へのリンク

---

## 7. cross references

**LLM 生成の `article_num` はリンク先決定に単独では使用しない**
（実測: 665件中、他法令を指す ref 34件、空文字 10件、表記ゆれ `_` `-` `の` が混在）。

- `ref` が法令名から始まる他法令参照はリンクしない
- `ref` に「附則」が含まれるものはリンクしない
- 各ページの `label` と `display_num` から同法令内の条文別名表を作る
- `ref` がその別名で始まり、対象 slug が実在し、自己参照でない場合だけ内部リンクする
- `article_num` は**補助検査**として使い、正規化した値が ref から解決した対象と
  矛盾する場合はリンクしない
- 解決不能な参照はテキスト表示に留める
- 解決数・未解決数を生成ログへ出す

---

## 8. フロントエンド

新規:
- `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx`
- `frontend/components/article-text.tsx`
- `frontend/components/article-history.tsx`
- `frontend/components/article-links.tsx`

変更:
- `frontend/lib/types.ts` / `frontend/lib/data.ts` / `frontend/app/sitemap.ts`
- `frontend/app/law/[lawId]/page.tsx` / `frontend/app/diff/[diffId]/page.tsx`
- `frontend/components/diff-viewer.tsx`

`data.ts` に追加: `getArticleLawIds()` / `getArticleData(lawId)` /
`getArticleParams()` / `findArticle(lawId, slug)`。
`generateStaticParams()` は生成物の slug をそのまま返し、空・重複があればビルドを落とす。

ページ構成:
1. パンくず
2. `法令名 第N条（caption）`
3. **現在の条文（YYYY年M月D日時点）** ← 「現在の条文」と断定しない
4. 現行本文に対応する説明（版不一致なら未収録表示）
5. 削除条文のみ、改正直前の条文
6. 改正履歴
7. 関連する条文
8. 法令全体の改正履歴へのリンク

民法754条のように現行ノードから caption を取得できないページでは、
metadata に**空括弧や推測した caption を入れない**。

---

## 9. metadata / canonical / 重複

- `/article` と `/diff` はそれぞれ**自己参照 canonical**。どちらも noindex にしない
- 条文ページの title は 法令名・条番号・取得できた caption・改正年 **だけ**から機械生成する
- description は「取得日時点の条文」「収録済み改正年」を述べるに留め、
  annotation の法的主張をコピーしない
- sitemap へ全条文ページを追加。`lastModified` は `source.asof`
- `/law/<lawId>` に「改正された条文」一覧を追加し、章節単位でグループ化する。中間ページは作らない
- `/diff` の各本則カードに条文ページへのリンクと固有 anchor を追加する
- 条文ページの履歴カードから対応する `/diff#anchor` へ戻れるようにする
- **`/diff` の本文・レイアウトは変更せず、見出しのリンクと anchor だけ追加する**

---

## 10. 検証

### Python 単体テスト（`tests/test_articles.py`）

- fetch 失敗時に非ゼロ終了し、保存 0 件
- `law_full_text` 欠落時に保存 0 件
- 全対象法令を検証し終える前に公開しない
- JST 日付が途中で変わった場合に保存 0 件
- slug 変換と範囲拒否
- 附則除外 / 未施行 diff 除外
- 本則 0 件の法令は成功・ファイルなし
- 変更履歴の降順 / `117_2_2` の複数改正
- `753:754` の diff 範囲エントリ除外
- 削除範囲は本文が「削除」の場合だけ解決
- **現行本文と `paragraphs_after` の一致・不一致判定**
- **不一致時に `current_summary` が生成されない**
- **廃止刑名を含む不整合 summary が現行説明にならない**
- 他法令・附則・自己参照を内部リンクしない

### 出荷データ検査（`tests/test_shipped_data.py` へ追加）

- articles ファイルが1件以上存在する
- `source.asof == fetched_at` の JST 日付 / `fetched_at` が `+09:00` 付き ISO 8601
- `law_revision_id` と `amendment_enforcement_date` が存在する
- `amendment_enforcement_date <= asof`
- 全ページの現行本文が非空
- slug が正規形・一意
- diff から導いた対象集合と出荷された `(law_id, article_num)` 集合が一致
- `current_summary` があるページは本文一致ゲートを通っている
- 削除ページは `former` と `merged_deleted` を持つ
- **ページ総数は JSON から導出し、固定値 163 をテストへ書かない**

### 採用しない検査（理由付き）

- **timeline との施行日比較**: 2つの API の施行日軸が一致しない（実測: 刑法は
  timeline 2026-05-22 / law_data 2026-05-21、マイナンバー法は 2026-08-22 / 2026-07-17）。
  採用すると初日から2法令が赤になり、人はまず比較を緩めるので受け入れ基準が空になる。
- **壁時計依存の期限切れテスト（180日で CI が赤）**: 現行108テストは0.87秒で全部決定的。
  この1本だけが今日の日付で結果が変わり、赤の直し方がネットワーク再取得と再コミットになる。
  CI はネットワークに出ない方針なので CI 内では直せない。
  ページに「取得日時点」を出しているので期限切れでも嘘にはならない。

一次保証は「生成時に `law_data?asof=today` を直接取得し、そのレスポンスの
`revision_info` を保存すること」。オフライン CI は provenance の形式と内部整合だけを検査する。

### 受け入れコマンド

```bash
uv run pytest
uv run python scripts/articles.py --all
uv run pytest tests/test_shipped_data.py
cd frontend && npm run lint
cd frontend && npm run build
```

静的ページ数は、生成 JSON の slug 数と `frontend/out/law/*/article/*` の HTML 数が
一致することを確認する。

---

## 11. 仮説検証

一括投入は維持する。**n=4 の弱い仮説であることを設計文書と計測記録に明記する。**

投入8週後に次を確認する:

- `/law/*/article/*` の表示回数・クリック・CTR・平均順位
- クエリが条文閲覧意図か、e-Gov へのナビゲーション意図か
- インデックス済みページ数
- 「検出・インデックス未登録」の件数
- `/diff` と条文ページの同一クエリでの競合
- 現行説明あり／履歴説明のみのページ間の差

**事前に noindex や削除の数値閾値は置かない。** 母数・インデックス状況・クエリ意図を
分けて評価してから次の判断をする。
（設計案 B が提案した「200 imp 未満なら noindex / 5 クリック以上なら維持」は
統計的根拠が無いため裁定で却下された。）

---

## 12. 残存リスク

- **annotation 自体の意味的誤り**: 本文一致は**版の一致しか保証しない**。
  LLM の説明が本文を正しく要約しているかは判定できない。
- **現行説明が一部欠ける**: 実測で162条文中30条文。新しい LLM 生成を禁止する以上、
  これらを現在の説明として安全に埋める手段はない。**誤った説明より明示的な未収録を選ぶ。**
- **削除条文の caption 欠落**: 民法754条の「夫婦間の契約の取消権」は現行ノードにも
  diff JSON にも残っていない。過去本文を追加取得しない限り、
  **検索上いちばん重要な語を title へ安全に入れられない**（GSC 可視クエリがこの語を含む）。
- **生成後の改正**: `asof` 表示により虚偽にはしないが、自動再生成の頻度は未決。
- **section_path の版ずれ**: 既存 diff 由来なので、その後の編章移動には追随しない。
  法的内容ではないがパンくず補助表示が古くなる可能性。
- **仮説そのもの**: 可視クエリに「e-gov」が含まれるため、条文閲覧ではなく
  特定サイトへのナビゲーション意図である可能性が残る。

---

## 13. 別 issue にするもの（本仕様に含めない）

1. `diff.py::find_articles` の caption 上書きバグ（`ArticleTitle` が `ArticleCaption` を消す）
2. 出荷済み diff を最新施行版まで追いつかせる（12法令すべてが5〜24か月遅れ）。
   §4 のゲートで「未収録」になる30条文は、これを直せば埋まる
3. 週次の live verification / 自動更新 PR（§12 の「生成後の改正」に対する機械的な催促）

---

## 付録: Gate 1 の担当表

| 役 | 担当 | 結果 |
|---|---|---|
| 裁定（Step 1.5 で予約） | codex | 完走。verdict.md（17.7KB）を出力 |
| draft A | Claude（親セッション） | 完了 — design-claude.md |
| draft B | fresh Claude #1 | 完了 — design-codex.md |
| critique of A | fresh Claude #2 | 完了 — critique-of-claude.md |
| critique of B | fresh Claude #3 | 完了 — critique-of-codex.md |

**逸脱**: grok が未認証（デバイス認証待ちで exit 124）だったため枠切れ扱いとし、
codex を裁定席に予約。結果として**設計案が両方とも Claude 族**になった。
案の多様性は落ちたが、裁定席は異族で確保されている。

**周回**: R0 → R1 → 裁定で1周。critique 2本が独立に同じ根
（本文と解説の版ズレ）へ到達したため、CLAUDE.md の
「同じ根の指摘が2回出たら spec へ戻す」に従い、実装へ進まず人へ判断を上げた（§0-3）。
