# 設計: `/law` ページへの「最近の改正をわかりやすく」解説の追加（SEO強化 B案）

- 日付: 2026-06-09
- 関連: GSC/GA4分析（imp急増・CTRほぼ0、`/law`改正履歴ページが勝ち型）、canonical修正(commit c83dd62)の後続施策

## 背景・目的

GSC分析の結論：
- 表示回数(imp)は4月～25/日 → 6月～60-93/日へ急増しているが、クリックはほぼ0（CTR最適化が最大レバレッジ）。
- `/law/{lawId}`（改正履歴）ページが唯一クリックを獲得（「不動産登記法改正 履歴」で順位3.5・CTR15%）。`/diff/`より検索意図に合致。
- 「○○法改正 わかりやすく」「○○法 改正 履歴」が有望クエリ。「不動産登記法 改正 わかりやすく」は順位45＝未対応。

**目的**：`/law`ページに「最近の改正をわかりやすく」長文解説を追加し、上がってきた露出を実クリックに変える。検索意図＝「最近この法律はどう変わったか」を平易に説明する。

## スコープ

- **Phase 1（本spec）**：実績上位4法令のみ生成・検証する。
  - 不動産登記法 `416AC0000000123`（順位3.5・クリック実績）
  - 民法 `129AC0000000089`（858impの最大露出源）
  - 労働基準法 `322AC0000000049`（改正履歴で露出開始）
  - 道路交通法 `335AC0000000105`（wwwで露出）
- **対象外（将来）**：残り法令への横展開はPhase1の効果をGSCで確認後に判断。

## アーキテクチャ方針

既存の `law_summary.py`（Claudeで`summary`を生成→timeline JSONに格納→`/law`ページで描画）と同一の疎結合パターンを踏襲する。データ生成（Python/Claude）とレンダリング（Next.js）は分離。

```
timeline.py → data/timelines/{law_id}.json
            → explainer.py (Claude, 新規) → 同JSONに explainer フィールド追記
            → frontend/public/data/timelines/{law_id}.json
            → /law/[lawId]/page.tsx が描画
```

## データ構造

`lib/types.ts` の `LawTimeline` に optional フィールドを追加（**未生成の法令は従来表示のまま＝後方互換**）。

```ts
export interface ExplainerChange {
  year: string;      // 例: "2024"
  title: string;     // 改正の通称。例: "相続登記の義務化"
  what: string;      // 何が変わったか（平易な1-3文）
  why?: string;      // なぜ変わったか（背景）。根拠(diff/pr_summary)がある場合のみ生成。無ければ省略
  impact?: string;   // 私たちへの影響。根拠がある場合のみ生成。無ければ省略
  grounded: boolean; // 条文差分(pr_summary)に基づくか。falseは施行日・改正法名のみ確認済みの軽量エントリ
}

export interface ExplainerFaq {
  q: string;
  a: string;
}

export interface LawExplainer {
  intro: string;                  // 導入2-3文
  recent_changes: ExplainerChange[]; // 最近の主要改正 2-4件（改正法/トピック単位に集約）
  faq: ExplainerFaq[];            // よくある質問 0-4件（欠落/null時は[]に正規化）
}

export interface LawTimeline {
  // ...既存フィールド
  explainer?: LawExplainer;
}
```

JSON例:
```jsonc
"explainer": {
  "intro": "不動産登記法は近年、相続登記の義務化など大きな改正が続いています。…",
  "recent_changes": [
    {
      "year": "2024",
      "title": "相続登記の義務化",
      "what": "相続を知った日から3年以内の登記が必須に。…",
      "why": "所有者不明土地の増加が社会問題化したため。…",
      "impact": "相続人は期限内の手続きが必要。怠ると過料。…"
    }
  ],
  "faq": [
    { "q": "相続登記の義務化はいつから？", "a": "2024年4月1日から施行されています。" }
  ]
}
```

## レンダリング

- 新コンポーネント `components/law-explainer.tsx`（page.tsx肥大化防止）。
- 配置：`/law/[lawId]/page.tsx` の「この法律について」(`summary`)カードの直後。
- 既存のTailwind/カードスタイル（`border`/`rounded-lg`/`bg-[var(--muted)]`/Iconコンポーネント）を踏襲。
- 構成：
  - `<h2>{law_title}の最近の改正をわかりやすく</h2>`（「○○法改正 わかりやすく」クエリに直撃する見出し）
  - `intro` 段落
  - `recent_changes` を「年・タイトル」見出し＋「何が変わった？」を表示。`why`/`impact`は値がある場合のみ表示（`grounded:false`では省略される）
  - `faq` を Q&A リストで表示（`faq`が空配列なら非表示）
  - AI生成の明示ラベル（about方針との一貫性）
- `explainer` が undefined の法令ではセクション自体を描画しない。

### meta description

- `/law/[lawId]/page.tsx` の `generateMetadata` で、`explainer.intro` があればそれを description に優先採用（無ければ従来通り `summary.description`）。「最近の改正」「わかりやすく」がSERP説明文に載るようにする。
- title は前コミット `c83dd62` で対応済み（`{法令名}の改正履歴｜全N回の改正一覧`）。本specでは変更しない。

### 構造化データ（優先度・低）

- **FAQリッチリザルトは政府機関・医療系の権威サイト限定で、lexdiffは対象外**。よってFAQPage JSON-LDはCTR改善の主要施策とせず、Phase1の成功条件・検証項目には含めない。
- 実装としては、`faq`が1件以上ある場合に `FAQPage` JSON-LD を出力すること自体は任意（セマンティック補助）。Phase1では**スコープ外**とし、FAQ本文（オンページのテキスト）のみ提供する。将来必要になれば `components/faq-jsonld.tsx` で追加。

## 生成スクリプト `scripts/explainer.py`

- `law_summary.py` を踏襲（`load_env`、`data/timelines/{law_id}.json`読み込み、生成、`data/` と `frontend/public/data/` の両方に書き戻し）。

### 入力の集約と根拠付け（hallucination対策の中核）

timelineをそのまま渡さない。以下の前処理を行う：

1. **改正法/トピック単位に集約**：同一 `amendment_law_title` が複数の施行日で並ぶケースや、技術的な整理法（「○○法の施行に伴う関係法律の整理等に関する法律」等）を1件に畳む。`diff_id:null`が大半なので、件数ではなく「市民に意味のある改正」を2-4件選ぶ。
2. **diff有改正を優先＆根拠付与**：`diff_id` のあるエントリは対応する `data/diffs/{diff_id}.json`（または `frontend/public/data/{diff_id}.json`）の `pr_summary`（title/summary/background/impact/key_changes）を入力に含め、`grounded:true` とする。これらは `why`/`impact` を生成してよい。
3. **diff無改正は抑制**：`diff_id:null` のエントリは `amendment_law_title`・`enforcement_date` のみ確認済みとして扱い、`grounded:false`。`what` は改正法名から言える範囲に留め、**`why`/`impact` は生成しない（省略）**。
4. recent_changes は新しい施行日順。`grounded:true`（実質的改正）を優先的に採用する。

- 入力プロンプト材料：`law_title`、`law_num`、`category`、`summary.description`、上記で集約・根拠付けした改正リスト。
- 出力：`explainer` JSON（上記スキーマ）。コードフェンス除去・`json.loads`は`law_summary.py`と同じ堅牢化を流用。`faq`欠落/`null`は`[]`に、`why`/`impact`の空文字は未設定として正規化。
- **モデル**：`claude-sonnet-4-6`（最新Sonnet。長文品質とコストのバランス。既存`law_summary.py`の`claude-sonnet-4-20250514`から更新）。
- **プロンプト方針**：日本語SEO記事の作法に沿う。
  - 見出し・本文に検索意図の語（「○○法 改正」「わかりやすく」「いつから」）を自然に含める。
  - 専門用語を避け日常生活との関わりで説明（既存summaryの方針と一貫）。
  - **提供データに無い事実（背景・影響・数値・期限）は断定しない**。`grounded:false` の改正では背景/影響を書かない。不確実な点は書かない（書かない方を選ぶ）。
  - 各フィールドの文字数目安：intro 80-150字、what 40-100字、why/impact 各40-100字、faq.a 40-120字。
- 既存の `requirements.txt` / `pyproject.toml`（anthropic）で追加依存なし。

## テスト・検証

### 自動チェック（機械的に落とす）
`explainer.py` 内（または小スクリプト）で生成JSONを検証し、満たさなければエラー終了：
- 必須キー（`intro`/`recent_changes`/`faq`）の存在と型。
- `recent_changes` は1-4件、各要素に `year`/`title`/`what`/`grounded`。`grounded:false` の要素は `why`/`impact` を持たないこと。
- 文字列長レンジ（intro/what/why/impact/faq）。空文字・`null`の混入なし（`faq`欠落は`[]`に正規化済み前提）。
- `year` が4桁数字、対象法令の施行年と矛盾しない（timelineの年集合に含まれる）。

### 事実性レビューゲート（公開前必須・手動）
- Phase1の4法令は**1件ずつ人手でレビュー**し、各 `recent_changes`/`faq` を次の根拠と突合：施行日・改正法名（timeline）、`grounded:true`は `pr_summary`。
- 突合できない断定（数値・期限・因果）が1つでもあれば、その記述を削るか再生成する。**未確認の記述を残したまま公開しない**。
- AI生成の明示ラベルは既存about方針に準拠（免責は補助であって、公開可否の担保は上記レビューが負う）。

### ビルド・互換
- `npm run build` がエラーなく通る。
- ビルド出力 `out/law/{id}.html` に `<h2>…わかりやすく</h2>` と本文が含まれることを確認。
- `explainer` 未生成の法令ページが従来通り描画される（後方互換）ことを確認。

## 成功条件・観測（Phase1）

- **観測期間**：本番反映後 約2-3週間（Googleの再クロール・再評価を待つ）。GSC/GA4はmy-mcp-server（GSC alias `lexdiff`, GA4 property 528978508）で取得。
- **主要指標**（4法令の `/law` ページに限定して観測）：
  - クリック数・CTR（最重要。現状ほぼ0からの改善）。
  - 「○○法 改正 わかりやすく」「○○法 改正 履歴」等クエリの掲載順位とクリック有無。
  - 表示回数（imp）とインデックス状況。
- **判断基準**：4法令は母数が小さくCTRが揺れやすいため、CTR単独でなく「クリック数の増加」と「対象クエリでの順位上昇（特に2ページ目→1ページ目）」を併せて見る。明確な改善が見えれば残り法令へ横展開、横ばいならプロンプト/構成を見直す。
- FAQリッチリザルトはlexdiffが対象外のため**成功条件に含めない**。

## 非対象（YAGNI）

- 全法令への一括生成（Phase1の効果確認後）。
- `/diff` ページ側のコンテンツ追加。
- FAQPage JSON-LD（lexdiffはリッチリザルト対象外。将来必要時に追加）。
- `recent_changes`/`faq` ごとの確認者・確認日・公開可否などのprovenance管理（Phase1は4法令を手動レビューするため過剰）。
- 多言語・履歴差分の自動更新ワークフロー。

## 影響ファイル

- 新規: `scripts/explainer.py`, `frontend/components/law-explainer.tsx`
- 変更: `frontend/lib/types.ts`, `frontend/app/law/[lawId]/page.tsx`（`law-explainer`描画＋`generateMetadata`のdescriptionを`explainer.intro`優先に）
- データ: `data/timelines/{4法令}.json` と `frontend/public/data/timelines/{4法令}.json`
