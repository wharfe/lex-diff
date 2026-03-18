# lexdiff — Law Amendments, Visualized

**[lexdiff.com](https://lexdiff.com)** | [🇯🇵 日本語版はこちら / Japanese](./README.ja.md)

GitHub-style diff viewer for Japanese law amendments. See what changed in the law, who proposed it, and why — at a glance.

## What It Does

- **Diff view** — Shows law amendments in familiar `+/-` format, article by article
- **Timeline** — Git log-style history of all amendments to a law
- **AI annotations** — Plain-language summaries of what each change means (powered by Claude)
- **Proposer info** — Who submitted the bill, which minister, which committee reviewed it
- **Life themes** — Browse laws by topics that matter to you (marriage, work, driving, privacy...)

## Why

Laws change frequently, but there's almost no UI for tracking *what* changed, *when*, and *why*. Legal texts are published, but comparing versions is left to professionals. lexdiff brings the developer experience of code review to legislation.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS |
| **Deployment** | Vercel (SSG) |
| **Data pipeline** | Python 3.13+ (managed with uv) |
| **AI annotations** | Claude API (Anthropic) |
| **Data source** | [e-Gov Law API v2](https://laws.e-gov.go.jp/api/2/) (Digital Agency of Japan) |
| **Proposer data** | [NDL Diet Records API](https://kokkai.ndl.go.jp/) |

## Getting Started

### Prerequisites

- Node.js 22+
- Python 3.13+ (via [uv](https://docs.astral.sh/uv/))
- Anthropic API key (for AI annotations)

### Setup

```bash
# Clone
git clone https://github.com/wharfe/lex-diff.git
cd lex-diff

# Python dependencies
uv sync

# Frontend dependencies
cd frontend
npm install
```

### Data Pipeline

```bash
# 1. Fetch law data (before/after a specific amendment)
uv run python scripts/fetch.py <law_id> <date_before> <date_after>

# 2. Compute structural diff
uv run python scripts/diff.py <law_id> <date_before> <date_after>

# 3. Generate AI annotations (requires ANTHROPIC_API_KEY in .env)
uv run python scripts/annotate.py data/diffs/<diff_file>.json

# 4. Generate amendment timeline
uv run python scripts/timeline.py <law_id>

# 5. Enrich with proposer info from NDL
uv run python scripts/enrich.py

# 6. Generate law summary
uv run python scripts/law_summary.py <law_id>
```

### Example: Civil Code (共同親権改正)

```bash
uv run python scripts/fetch.py 129AC0000000089 2024-03-31 2024-04-01
uv run python scripts/diff.py 129AC0000000089 2024-03-31 2024-04-01
uv run python scripts/annotate.py data/diffs/129AC0000000089_2024-03-31_2024-04-01.json
```

### Development Server

```bash
cd frontend
npm run dev -- -p 3002
```

## Project Structure

```
/
├── scripts/            Python data pipeline
│   ├── fetch.py        Fetch law data from e-Gov API
│   ├── diff.py         Compute structural diff
│   ├── annotate.py     Generate AI annotations (Claude)
│   ├── timeline.py     Build amendment timeline
│   ├── proposer.py     Fetch bill proposer from NDL API
│   ├── enrich.py       Enrich data with proposer info
│   └── law_summary.py  Generate AI law summary
├── frontend/           Next.js application
│   ├── app/            Pages (home, /law, /diff, /theme, /about)
│   ├── components/     UI components
│   ├── lib/            Types, data utilities, theme config
│   └── public/data/    Static data for SSG
├── CLAUDE.md           AI assistant instructions
└── pyproject.toml      Python project config
```

## How It Works

1. **e-Gov Law API v2** provides law text at any point in time via the `asof` parameter
2. Python scripts fetch before/after versions and compute article-level structural diffs
3. Claude AI generates plain-language summaries for each change
4. NDL Diet Records API identifies who submitted each amendment bill
5. Next.js renders everything as a static site

## Data Source

- Law text from [e-Gov Law API v2](https://laws.e-gov.go.jp/api/2/) (Digital Agency). No authentication required.
- Bill proposer data from [NDL Diet Records API](https://kokkai.ndl.go.jp/)
- Law texts are not copyrighted (Copyright Act Article 13)
- AI-generated summaries are clearly labeled as such

## Related Project

- **[OpenGIKAI](https://github.com/wharfe/open-gikai)** — Restructures parliamentary proceedings (Diet sessions, PM press conferences, government councils) into a modern thread format. lexdiff shows *what changed* in the law; OpenGIKAI shows *how it was debated*.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](./LICENSE)
