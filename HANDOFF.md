# HANDOFF

<!-- /wrap-up が更新する引き継ぎファイル。単一ファイルを上書き更新（履歴は vault にある） -->

- 更新: 2026-09-22 22:30 (JST)
- ブランチ: `feat/article-pages`（main から 15 commits。**追跡リモート未設定・PR なし**）

## ゴール

issue #4 — `/diff` がサイト最大の表示回数を集めながらクリック 0 の状態を解く。
条文 1 本 = 1 ページを新設し、「現在の条文・いつどう変わったか・平易な解説・関連条文」を
1 画面にまとめて、条文閲覧の検索意図に応える。

## 現在地

**計画 10 タスク中 8 つ完了。Python パイプラインと実データは出来ている。フロントエンドが未着手。**

- `scripts/articles.py` 完成（純粋関数 + `main()`）。`tests/test_articles.py` 78 件
- 実データ生成済み: `frontend/public/data/articles/*.json` = **11 法令・163 条文**
  （労働基準法は本則の改正が 0 件のためファイル無し。これは正常）
  - うち **36 件**は版不一致で `current_summary` が null（解説を出さない）
  - リンク 497 本、うちページを持つものが 375 本
- `tests/test_shipped_data.py` に出荷データ検査を追加。`uv run pytest` = **267 件緑**
- 実装計画: `docs/superpowers/plans/2026-09-22-article-pages.md` の **Task 9 から**
- 実行記録・裁定の全リスト: `.superpowers/sdd/2026-09-22-article-pages/progress.md`
  （git 管理外。`git clean -fdx` で消えるので、必要なら先に読む）

## 次の一手

1. `superpowers:subagent-driven-development` で **Task 9**（フロントエンドの型・読み出し・
   ページ本体）から再開する。ledger が `.superpowers/sdd/2026-09-22-article-pages/progress.md`
   にあるので、まずそれを読む（完了タスクを再実行しないため）
2. **Task 9 の計画コードはそのまま書くと壊れる。** 下の「注意」の 1 番を必ず反映する
3. Task 10（`/law` の条文一覧・`/diff` カードの anchor とリンク・sitemap）
4. 受け入れコマンドを通す:
   `uv run pytest` → `uv run python scripts/articles.py --all` →
   `uv run pytest tests/test_shipped_data.py` → `cd frontend && npm run lint && npm run build`
5. 生成 JSON の slug 総数と `frontend/out/law/*/article/*` の HTML 数が一致することを確認
   （**163 という固定値をテストに書かない**）
6. `/code-gate`（(B) 区分なので Gate3 必須）
7. push と PR は未実施。`git push -u origin feat/article-pages` するか、main へ直接入れるかは判断待ち

## 注意

1. **`current.status` は 3 値になった** — `present` / `deleted` / `merged_deleted`。
   計画の Task 9 のコードは 2 値前提で `merged_deleted` しか分岐していない。**そのまま書くと
   墓標ページ（民法733・民法746・刑法178）が生きた条文のように表示される。**
   - `merged_deleted` = 範囲ノードに畳まれた（民法753・754）。
     文面は「{displayNum}は「{source_label}」として欠番になっています。」
   - `deleted` = 単独で本文が「削除」の一語（民法733・746・刑法178）。**別の文面が要る** —
     何かに畳まれたのではなく、単に廃止された条文
2. **`former`（改正直前の条文）が、改正 type が `deleted` でないページにも付く。**
   墓標 5 ページ全部が `former` を持つ
3. **24 ページが `caption` 空。** 見出しで空の `（）` を描画しないこと
4. **`cross_references` の `context`** は、リンク先の版が古いときは Python 側で落としてある
   （空文字）。フロント側で「context があるときだけ出す」形にすること
5. **`diff.py` を変更しない。** `find_articles` の caption 取りこぼしは既知バグだが対象外
6. **`scripts/articles.py --all` は毎回 e-Gov へ 11 リクエストする。** 生成済みなので
   フロント作業中に走らせ直す必要は無い。走らせるなら `LookupError` は**止まる**合図
   （施行済み改正があるのに今日の本文に無い条文 → 飛ばさず人へ）
7. 試して**不採用**にしたもの（spec §10。再提案しない）: e-Gov の `?elm=Article_306` ／
   timeline との施行日比較 ／ 壁時計依存の期限切れテスト
8. 関連 issue: #23（出荷 diff が全法令で遅れている）。マイナンバー法は 6 条すべて解説が
   落ちているが、これはゲートが正しく働いた結果で、直すなら #23 側
