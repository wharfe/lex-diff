# HANDOFF

<!-- /wrap-up が更新する引き継ぎファイル。単一ファイルを上書き更新（履歴は vault にある） -->

- 更新: 2026-09-22 (JST)
- ブランチ: `main`（push 済み `f94fafe`。PR なし・実装未着手）

## ゴール

issue #4 — `/diff` がサイト最大の表示回数を集めながらクリック 0 の状態を解く。
条文 1 本 = 1 ページ（現在 163 枚）を新設し、「現在の条文・いつどう変わったか・平易な解説・
関連条文」を 1 画面にまとめて、条文閲覧の検索意図に応える。

## 現在地

- **Gate 1 完了・Gate 2 完了（上限 3 周で打ち切り）。実装は 1 行も書いていない。**
- 確定仕様: `docs/design-debate/article-pages/spec.md`
- 実装計画: `docs/superpowers/plans/2026-09-22-article-pages.md`（10 タスク・TDD・
  全ステップに実コード・赤→緑の確認コマンド付き。zero context の実装者向けに書いてある）
- Gate 1 の記録は同じディレクトリの `brief.md` / `design-claude.md` / `design-codex.md` /
  `critique-of-claude.md` / `critique-of-codex.md` / `verdict.md`
- Gate 2 の記録は `gate2-grok.md`（周回1）/ `gate2-grok-r2.md`（周回2）/ `gate2-grok-r3.md`（周回3）と、
  計画ファイル末尾の 3 つの「Gate 2 の記録」節

**仕様の中心は 2 つだけ憶えておけばよい:**

1. **版整合ゲート**（spec §4）— 出荷済み diff は法令から 5〜24 か月遅れている。
   解説が書かれた時点の条文と今日の条文を照合し、**不一致なら解説ブロックを丸ごと落とす**
   （実測: 162 条中 30 条が該当）。関連条文リンクも同じゲートに掛かる
2. **フィールドの出所表**（spec §5）— 「現在」と名乗るブロックに出るものは、
   今日の取得由来か、ゲートを通ったものだけ。新しいフィールドは表に行を足してから実装する

## 次の一手

1. `docs/superpowers/plans/2026-09-22-article-pages.md` の **Task 1** から実装する。
   `superpowers:subagent-driven-development`（タスクごとに fresh subagent + 間でレビュー）を推奨
2. Task 8 で実データを生成する（e-Gov へ 11 リクエスト）。`LookupError` が出たら**止まる** —
   「施行済みの改正があるのに今日の本文に無い」条文なので、条番号と法令を報告して人に上げる
3. 全タスク後に受け入れコマンドを通す:
   `uv run pytest` → `uv run python scripts/articles.py --all` →
   `uv run pytest tests/test_shipped_data.py` → `cd frontend && npm run lint && npm run build`
4. 生成 JSON の slug 総数と `frontend/out/law/*/article/*` の HTML 数が一致することを確認する
   （**163 という固定値をテストに書かない**）
5. `/code-gate`（(B) 区分なので Gate3 必須）

## 注意

- **Gate 2 は PASS ではなく上限 3 周による打ち切り。** 周回 3 の修正自体はレビューを受けていない。
  Gate 3 で拾う
- **`diff.py` を変更しない。** `find_articles` の caption 取りこぼしは既知バグだが本計画の対象外。
  条文ページ側は `extract_article_body()` で `ArticleTitle` と `ArticleCaption` を別々に読む
- **`format_paragraph` は `ParagraphNum` を読み飛ばす。** 差分ビューでは正しいが条文ページでは
  項番号が消える。`Paragraph@Num` を `num`、`ParagraphNum` を `mark` として別に読むこと
  （複数項の改正エントリは 107 件）
- **削除条文は `find_section_path(tree, "753")` が `None` を返す。**
  `current["source_article_num"]`（`753:754`）で引く
- **`cross_references` の `article_num` を単独で信じない。** LLM の自由記述で、
  他法令 34 件・空 10 件・表記ゆれ混在。条名（`ref`）で解決し `article_num` は veto にだけ使う
- 試して**不採用**にしたもの: e-Gov の `?elm=Article_306`（実在するが provenance が
  163 個に散る）／ timeline との施行日比較（2 API の施行日軸が違い初日から 2 法令が赤）／
  壁時計依存の期限切れテスト（CI 内で直せない）。**再提案しない**（理由は spec §10）
- 関連 issue: #23（出荷 diff が全法令で遅れている。直すとゲートに落ちる 30 条の大半が埋まる）
