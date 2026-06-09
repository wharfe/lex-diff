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
  why: string;       // なぜ変わったか（背景・1-2文）
  impact: string;    // 私たちへの影響（1-2文）
}

export interface ExplainerFaq {
  q: string;
  a: string;
}

export interface LawExplainer {
  intro: string;                  // 導入2-3文
  recent_changes: ExplainerChange[]; // 最近の主要改正 2-4件
  faq: ExplainerFaq[];            // よくある質問 2-4件（0件可）
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
  - `recent_changes` を「年・タイトル」見出し＋「何が変わった？ / なぜ変わった？ / 私たちへの影響」の3点で表示
  - `faq` を Q&A リストで表示（`faq`が空配列なら非表示）
  - AI生成の明示ラベル（about方針との一貫性）
- `explainer` が undefined の法令ではセクション自体を描画しない。

### 構造化データ

- `faq` が1件以上ある場合、`/law`ページに `FAQPage` JSON-LD を出力（既存 `components/breadcrumb-jsonld.tsx` と同方式の `<script type="application/ld+json">`）。新コンポーネント `components/faq-jsonld.tsx`。
- `faq` が空なら出力しない。

## 生成スクリプト `scripts/explainer.py`

- `law_summary.py` を踏襲（`load_env`、`data/timelines/{law_id}.json`読み込み、生成、`data/` と `frontend/public/data/` の両方に書き戻し）。
- 入力プロンプト材料：`law_title`、`law_num`、`category`、`summary.description`（既存）、直近のtimelineエントリ数件（`amendment_law_title`・`enforcement_date`・`proposer.minister`）。
- 出力：`explainer` JSON（上記スキーマ）。コードフェンス除去・`json.loads`は`law_summary.py`と同じ堅牢化を流用。
- **モデル**：`claude-sonnet-4-6`（最新Sonnet。長文品質とコストのバランス。既存`law_summary.py`の`claude-sonnet-4-20250514`から更新）。
- **プロンプト方針**：日本語SEO記事の作法に沿う。
  - 見出し・本文に検索意図の語（「○○法 改正」「わかりやすく」「いつから」）を自然に含める。
  - 専門用語を避け日常生活との関わりで説明（既存summaryの方針と一貫）。
  - 事実は提供データ（改正法律名・施行日）に基づき、推測の断定を避ける。
  - 各フィールドの文字数目安：intro 80-150字、what/why/impact 各40-100字、faq.a 40-120字。
- 既存の `requirements.txt` / `pyproject.toml`（anthropic）で追加依存なし。

## テスト・検証

- 静的サイトのため自動テストは最小。検証は以下で行う：
  1. `explainer.py` を4法令に実行し、生成JSONがスキーマ通り（必須キー・型・件数範囲）であることを目視＋簡易バリデーション。
  2. `npm run build` がエラーなく通る。
  3. ビルド出力 `out/law/{id}.html` に `<h2>…わかりやすく</h2>` 本文と（FAQありの法令で）FAQPage JSON-LD が含まれることを確認。
  4. `explainer` 未生成の法令ページが従来通り描画される（後方互換）ことを確認。
- 生成内容は事実性をレビュー（誤りがあれば再生成 or 手修正）。AI生成の免責は既存about方針に準拠。

## 非対象（YAGNI）

- 全法令への一括生成（Phase1の効果確認後）。
- `/diff` ページ側のコンテンツ追加。
- 多言語・履歴差分の自動更新ワークフロー。

## 影響ファイル

- 新規: `scripts/explainer.py`, `frontend/components/law-explainer.tsx`, `frontend/components/faq-jsonld.tsx`
- 変更: `frontend/lib/types.ts`, `frontend/app/law/[lawId]/page.tsx`
- データ: `data/timelines/{4法令}.json` と `frontend/public/data/timelines/{4法令}.json`
