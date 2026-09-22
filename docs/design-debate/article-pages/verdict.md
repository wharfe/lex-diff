## 1. 判定

**設計案Bを勝者とする。** 決め手は、訂正後の実データに即して 163 ページを導出し、`753:754`、削除条文、法令単位の取得 provenance、TS 側で条番号を再解釈しない構成まで具体化している点である。Aは簡潔だが、固定値164、範囲エントリの不適切な展開、弱い鮮度検査、caption取得方法、TS/Python二重変換に問題がある。ただしBもそのままでは採用できない。最大の欠陥は、生成時の現行本文と既存 annotation の版を照合せず、実測で本文が変わった30条文に古い説明を「この条文は何をする条文か」と表示すること。したがって、Bの生成・provenance・URL・削除条文モデルを骨格にし、**現行本文と annotation の版整合ゲート**を必須条件として採用する。

## 2. 移植する部品

Aから次を移植する。

- **恣意的なGSC打ち切り値を置かない。**  
  Bの「200 imp未満ならnoindex」「5クリックなら維持」には統計的根拠がない。Aのように仮説の薄さを明示し、8週後の観測項目だけを事前定義する。

- **範囲エントリより個別エントリを優先する。**  
  `753:754` を753・754の履歴へ単純展開すると、754について書かれた誤った annotation が753へ混入する。個別エントリが存在する範囲エントリはページ・解説・履歴の入力から除外する。

- **履歴は必要最小限にする。**  
  条文ページには日付、改正法名、`change_description`、`/diff` へのリンクを載せる。unified diff本体は既存 `/diff` に残し、同じデータを複製しない。

- **`diff.py` の大規模リファクタリングを同じ変更に混ぜない。**  
  `lawtext.py` への関数移動は機能の必須条件ではない。新スクリプトは `walk_tags`、`extract_text`、既存の段落整形だけを利用する。

- **「取得日時点」の明示。**  
  ページ見出しは必ず「現在の条文（YYYY年M月D日時点）」とし、静的ページを無期限に「現在」と断定しない。

Bからは、法令全文を1法令1回取得する方式、`source` provenance、法令単位JSON、Pythonで確定したslug、削除条文の`merged`モデル、自己参照canonical、サイトマップ・内部リンク、生成物からページ数を導出する方式を維持する。

## 3. 確定仕様

### 3.1 対象とURL

- URLは `/law/<lawId>/article/<slug>`。
- 対象は、出荷済みdiffのうち次を満たすエントリから導く。
  - 本則である。
  - `date_after <= 生成時のJST日付`。
  - `article_num` が単独条番号であり、範囲形ではない。
- 現在の出荷データでは163ページ。件数はテストへ固定しない。
- 労働基準法のように対象本則が0件の法令は正常終了し、articlesファイルを作らない。
- slug変換はPythonだけで行う。
  - `306` → `306`
  - `308_2` → `308-2`
  - `117_2_2` → `117-2-2`
  - `:` を含む番号はslug化禁止。
- 日本語表記は本文用の `display_num` として生成する。
- TypeScript側に条番号・slug変換関数を作らない。

### 3.2 生成スクリプト

新規に `scripts/articles.py` を追加する。

```bash
uv run python scripts/articles.py <law_id>
uv run python scripts/articles.py --all
```

主な関数は以下とする。

| 関数 | 責務 |
|---|---|
| `collect_changes()` | 出荷済みdiffから対象条文と改正履歴を集める |
| `article_slug()` | 単独条番号をslugへ変換。範囲形は拒否 |
| `index_current_articles()` | `walk_tags(..., {"Article"}, stop_at={"SupplProvision"})` で現行本則を索引化 |
| `extract_article_body()` | ArticleTitle、ArticleCaption、Paragraphを分離して取り出す |
| `resolve_current()` | `present` / `merged_deleted` / エラーを判定 |
| `texts_match()` | 最新diff直後本文と現在本文の版整合を判定 |
| `resolve_cross_references()` | 同法令内の安全なリンクだけを確定 |
| `build_law_articles()` | 法令単位JSONを構築 |
| `validate_articles()` | 保存前検証 |
| `main()` | 取得、構築、検証、日付再確認、保存 |

再利用するもの:

- `fetch.fetch_law_data(law_id, asof)`
- `lawtext.walk_tags`
- `lawtext.extract_text`
- 既存の段落・Item整形処理

e-Govの`elm`取得は採用しない。1法令の全対象条文を1レスポンス・1 revisionで取得でき、12法令以下のリクエストで済み、既存取得器を変更しなくてよいためである。

### 3.3 取得と保存の原子性

生成順序は次のとおり。

1. JSTの `today` と開始時刻を取得。
2. 対象法令ごとに `fetch_law_data(law_id, today)` を1回呼ぶ。
3. APIレスポンスに `law_full_text` と `revision_info` がなければ失敗。
4. 全法令についてメモリまたは一時領域で生成・検証する。
5. 保存直前にJST日付を再確認する。
6. 日付が変わっていた場合は何も公開せず非ゼロ終了。
7. 全対象法令が成功した後だけ、各JSONを一時ファイルから原子的に置換する。

`--all` で1法令でも取得・構築・検証に失敗した場合、今回の実行で生成したファイルは一つも公開しない。途中まで成功した法令だけ更新する方式は採用しない。

出力先:

- `data/articles/<lawId>.json`
- `frontend/public/data/articles/<lawId>.json`

`.gitignore` に `data/articles/` を追加する。frontend側はコミット対象。

### 3.4 出力データ

法令ごとに次の形を持つ。

```json
{
  "law_id": "129AC0000000089",
  "law_title": "民法",
  "source": {
    "asof": "2026-09-22",
    "fetched_at": "2026-09-22T14:07:31+09:00",
    "law_revision_id": "...",
    "amendment_enforcement_date": "2026-06-24"
  },
  "articles": []
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
  "section_path": [],
  "current": {
    "status": "present",
    "source_article_num": "306",
    "paragraphs": []
  },
  "current_summary": {
    "text": "...",
    "evidence_date": "2026-04-01"
  },
  "former": null,
  "changes": [],
  "related_articles": []
}
```

決定事項:

- `label` と `caption` は今日取得したArticleノードから直接、別々に読む。
- `section_path` は最新の個別diffエントリから取る。
- `changes` は施行日降順。複数改正がある道路交通法`117_2_2`も同じ配列で扱う。
- `former` は個別エントリが`deleted`の場合だけ、そのエントリの`paragraphs_before`と`date_before`から作る。
- `former` の見出しは「今回の改正直前の条文」とし、法律制定時の元条文であるかのようには表示しない。
- diffの範囲エントリは`changes`へ入れない。

### 3.5 現行本文とannotationの版整合ゲート

これを出荷必須条件とする。

対象条文の最新の**個別**diffエントリについて、`paragraphs_after`と今日取得した本文を比較する。比較は段落番号と本文を対象とし、改行コード・末尾空白以外は正規化しない。

#### 本文が一致する場合

- `annotation.plain_summary` を `current_summary` として表示できる。
- 最新annotationのcross referencesを「関連する条文」の候補にできる。
- `current_summary.evidence_date` を記録する。
- ただし、現行本文に存在しない廃止刑名がsummaryに含まれる場合は一致扱いにせず、現在の説明から除外する。

#### 本文が一致しない場合

- `plain_summary` を「この条文は何をする条文か」として表示してはならない。
- `current_summary` は `null`。
- ページには機械的な案内として  
  「現行本文に対応する解説は未収録です。収録済み改正時点の説明は改正履歴で確認できます。」  
  と表示する。
- `plain_summary` は対応する履歴カード内へ移し、  
  「YYYY年M月D日改正直後の条文についての説明」  
  と時点を明示する。
- cross referencesも現在の関連条文とはせず、同じ履歴カード内で時点付き表示にする。

`change_description` は改正履歴内だけで使用し、必ず施行日・改正法名と同じカード内に置く。これにより「懲役」などの歴史的表現が現行制度の説明として読まれないようにする。

### 3.6 範囲ノードと削除条文

`753:754`のような範囲形はページを持たない。

#### diff側の範囲エントリ

- 同じdiff・同じ施行日に各構成員の個別エントリが存在する場合、範囲エントリはページ生成入力から除外する。
- 個別エントリのない範囲エントリを検出した場合は、自動展開せず生成を失敗させる。

#### 現行法側の範囲ノード

`resolve_current()` は次の順で解決する。

1. `article_num` 完全一致なら `present`。
2. 対象が個別diff上で`deleted`であり、範囲ノードがその番号を含み、かつノード本文が実質的に「削除」だけなら `merged_deleted`。
3. それ以外は`LookupError`。

育児介護休業法`36:52`のような広い範囲へ単に番号が入るだけでは、削除済みと判定しない。

削除条文ページは次の順に表示する。

1. 現在の姿  
   「第753条・第754条は『第七百五十三条及び第七百五十四条　削除』として扱われています（取得日時点）」。
2. 今回の改正直前の条文  
   日付と「現行法ではありません」を明示。
3. 改正履歴と既存annotation。
4. `/diff`へのリンク。

### 3.7 cross references

LLM生成の `article_num` はリンク先決定に単独では使用しない。

- `ref` が法令名から始まる他法令参照はリンクしない。
- `ref` に「附則」が含まれるものはリンクしない。
- 各ページの `label` と `display_num` から同法令内の条文別名表を作る。
- `ref` がその別名で始まり、対象slugが実在し、自己参照でない場合だけ内部リンクする。
- `article_num` は補助検査として使い、表記を正規化した値がrefから解決した対象と矛盾する場合はリンクしない。
- 解決不能な参照はテキスト表示に留める。
- 解決数・未解決数を生成ログへ出し、誤リンクを黙って作らない。

### 3.8 フロントエンド

新規:

- `frontend/app/law/[lawId]/article/[articleSlug]/page.tsx`
- `frontend/components/article-text.tsx`
- `frontend/components/article-history.tsx`
- `frontend/components/article-links.tsx`

変更:

- `frontend/lib/types.ts`
- `frontend/lib/data.ts`
- `frontend/app/sitemap.ts`
- `frontend/app/law/[lawId]/page.tsx`
- `frontend/app/diff/[diffId]/page.tsx`
- `frontend/components/diff-viewer.tsx`

`data.ts`には以下を追加する。

- `getArticleLawIds()`
- `getArticleData(lawId)`
- `getArticleParams()`
- `findArticle(lawId, slug)`

`generateStaticParams()` は生成物のslugをそのまま返す。空・重複があればビルドを失敗させる。

ページ構成:

1. パンくず
2. `法令名 第N条（caption）`
3. 現在の条文（取得日時点）
4. 現行本文に対応する説明。版不一致なら未収録表示
5. 削除条文のみ、改正直前の条文
6. 改正履歴
7. 関連する条文
8. 法令全体の改正履歴へのリンク

民法754条など現行ノードからcaptionを取得できないページでは、metadataに空括弧や推測したcaptionを入れない。

### 3.9 metadata、canonical、重複

- `/article` と `/diff` はそれぞれ自己参照canonical。
- どちらもnoindexにしない。
- 条文ページのtitleは、法令名・条番号・取得できたcaption・改正年だけから機械生成する。
- descriptionは「取得日時点の条文」「収録済み改正年」を述べるに留め、annotationの法的主張をコピーしない。
- sitemapへ全条文ページを追加し、`lastModified`は`source.asof`。
- `/law/<lawId>`に「改正された条文」一覧を追加し、章節単位でグループ化する。中間ページは作らない。
- `/diff`の各本則カードに条文ページへのリンクと固有anchorを追加する。
- 条文ページの履歴カードから対応する`/diff#anchor`へ戻れるようにする。
- `/diff`の本文・レイアウトは変更せず、見出しのリンクとanchorだけ追加する。

### 3.10 検証

Python単体テスト:

- fetch失敗時に非ゼロ終了し、保存0件。
- `law_full_text`欠落時に保存0件。
- 全対象法令を検証し終える前に公開しない。
- JST日付が途中で変わった場合に保存0件。
- slug変換と範囲拒否。
- 附則除外。
- 未施行diff除外。
- 本則0件の法令は成功・ファイルなし。
- 変更履歴の降順。
- `117_2_2`の複数改正。
- `753:754`のdiff範囲エントリ除外。
- 削除範囲は本文が「削除」の場合だけ解決。
- 現行本文と`paragraphs_after`の一致・不一致判定。
- 不一致時に`current_summary`が生成されない。
- 廃止刑名を含む不整合summaryが現行説明にならない。
- 他法令・附則・自己参照を内部リンクしない。

出荷データ検査:

- articlesファイルが1件以上存在する。
- `source.asof == fetched_at`のJST日付。
- `fetched_at`が`+09:00`付きISO 8601。
- `law_revision_id`と`amendment_enforcement_date`が存在する。
- `amendment_enforcement_date <= asof`。
- 全ページの現行本文が非空。
- slugが正規形・一意。
- diffから導いた対象集合と出荷された `(law_id, article_num)` 集合が一致。
- `current_summary`があるページは本文一致ゲートを通っている。
- 削除ページは`former`と`merged_deleted`を持つ。
- ページ総数はJSONから導出し、固定値163をテストへ書かない。

鮮度について、timelineとの施行日比較は採用しない。両APIの施行日軸が一致せず、timeline自体の鮮度も保証されないためである。生成時に`law_data?asof=today`を直接取得し、そのレスポンスの`revision_info`を保存することを一次保証とする。オフラインCIはprovenanceの形式と内部整合だけを検査する。

受け入れコマンド:

```bash
uv run pytest
uv run python scripts/articles.py --all
uv run pytest tests/test_shipped_data.py
cd frontend && npm run lint
cd frontend && npm run build
```

静的ページ数は、生成JSONのslug数と`frontend/out/law/*/article/*`のHTML数が一致することを確認する。

### 3.11 仮説検証

一括投入はbriefどおり維持する。n=4の弱い仮説であることを設計文書と計測記録に明記する。

投入8週後に次を確認する。

- `/law/*/article/*` の表示回数、クリック、CTR、平均順位。
- クエリが条文閲覧意図か、e-Govへのナビゲーション意図か。
- インデックス済みページ数。
- 「検出・インデックス未登録」の件数。
- `/diff`と条文ページの同一クエリでの競合。
- 現行説明あり／履歴説明のみのページ間の差。

事前にnoindexや削除の数値閾値は置かない。母数、インデックス状況、クエリ意図を分けて評価して次の判断を行う。

## 4. 残存リスク

- **annotation自体の意味的誤り**  
  本文一致は版の一致しか保証しない。LLM説明が本文を正しく要約しているかは判定できない。

- **現行本文に対応する説明が一部欠ける**  
  実測では162条文中30条文で本文差分がある。新しいLLM生成を禁止する以上、これらを現在の説明として安全に埋める手段はない。誤った説明より明示的な未収録を選ぶ。

- **削除条文のcaption欠落**  
  民法754条の「夫婦間の契約の取消権」は現行ノードにもdiff JSONにもcaptionとして残っていない。過去本文を追加取得しない限り、検索上重要な語をtitleへ安全に入れられない。

- **生成後の改正**  
  `asof`表示により虚偽にはしないが、自動再生成の頻度は未決。壁時計依存で通常CIを突然赤くする方式は採らない。必要なら別途、週次のlive verification／更新PRを設計する。

- **section pathの版ずれ**  
  `section_path`は既存diff由来なので、その後の編章移動には追随しない。法的内容ではないが、パンくず補助表示が古くなる可能性がある。

- **仮説そのもの**  
  可視クエリに「e-gov」が含まれるため、条文閲覧ではなく特定サイトへのナビゲーション意図である可能性が残る。

**完了**: 両案と相互批評を裁定し、設計案Bを版整合ゲート付きで統合した確定仕様を提示した。  
**次の一手**: 1. この仕様を実装計画へ分解する。2. 30件の版不一致を計画時の固定フィクスチャ候補として一覧化する。  
**検証**: repoの既存取得器、条文走査、caption処理、データ層、diff表示、保存方式、`.gitignore`を読み取り確認済み。ファイル変更・ネットワーク再取得は行っていない。
