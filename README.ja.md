# lexdiff — 法令改正の差分ビューア

**[lexdiff.com](https://lexdiff.com)** | [English](./README.md)

法律の改正履歴をGitHub風の差分表示で可視化するオープンソースプロジェクトです。いつ・どの条文が・誰によって・どう変わったかを、一目で追えます。

## 特徴

- **差分表示** — 条文の変更を `+/-` 形式で表示
- **改正履歴** — 法律の全改正をgit log風のタイムラインで一覧
- **AI注釈** — 各変更の意味をわかりやすく要約（Claude AI）
- **提出者情報** — 誰が法案を提出し、どの委員会で審議されたか
- **ライフテーマ** — 結婚・仕事・運転・個人情報など、生活に関わるテーマから法律を探せる

## なぜ作ったか

法律は頻繁に改正されますが、「何がどう変わったか」を追うUIがほとんど存在しません。法律の原文は公開されていますが、版の比較は専門家に委ねられています。lexdiffは、ソフトウェア開発のコードレビューと同じ体験を法令にもたらします。

日本の法律を改正するには「改正法」という別の法律が必要です。たとえば民法を変えるには「民法等の一部を改正する法律」を国会で可決する必要があります。lexdiffの改正履歴に法律名が並ぶのはこのためです。

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| **フロントエンド** | Next.js（App Router）、TypeScript、Tailwind CSS |
| **デプロイ** | Vercel（SSG） |
| **データパイプライン** | Python 3.13+（uv） |
| **AI注釈** | Claude API（Anthropic社） |
| **データソース** | [e-Gov法令API v2](https://laws.e-gov.go.jp/api/2/)（デジタル庁） |
| **提出者データ** | [NDL国会会議録API](https://kokkai.ndl.go.jp/) |

## セットアップ

```bash
# クローン
git clone https://github.com/wharfe/lex-diff.git
cd lex-diff

# Python依存関係
uv sync

# フロントエンド依存関係
cd frontend
npm install

# 開発サーバー
npm run dev -- -p 3002
```

### データパイプライン

```bash
# 1. 法令データ取得（改正前後の日付を指定）
uv run python scripts/fetch.py <法令ID> <改正前日付> <改正後日付>

# 2. 差分計算
uv run python scripts/diff.py <法令ID> <改正前日付> <改正後日付>

# 3. AI注釈生成（.envにANTHROPIC_API_KEYが必要）
uv run python scripts/annotate.py data/diffs/<ファイル名>.json

# 4. 改正履歴タイムライン生成
uv run python scripts/timeline.py <法令ID>

# 5. 提出者情報の付与（NDL API）
uv run python scripts/enrich.py

# 6. 法律の概要生成
uv run python scripts/law_summary.py <法令ID>
```

## データソース

- 法令データ: [e-Gov法令API v2](https://laws.e-gov.go.jp/api/2/)（デジタル庁）— 認証不要
- 提出者データ: [NDL国会会議録API](https://kokkai.ndl.go.jp/)
- 法令は著作権法第13条により著作権の対象外
- AI生成コンテンツは「Claude AIによる要約」と明示

## 関連プロジェクト

- **[OpenGIKAI](https://github.com/wharfe/open-gikai)** — 国会審議・首相記者会見・政府審議会などの公的な議論をスレッド形式で再構築するオープンソースの公共メディア。lexdiffが「法律の条文がどう変わったか」を見せるのに対し、OpenGIKAIは「その法律がどう議論されたか」を見せます。

## コントリビュート

コントリビューションを歓迎します。[CONTRIBUTING.md](./CONTRIBUTING.md) をご参照ください。

## ライセンス

MIT — [LICENSE](./LICENSE) をご参照ください
