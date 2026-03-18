# lex-diff - Project Instructions for Claude Code

## Project Overview

lex-diff is an open-source tool that visualizes Japanese law amendments in a GitHub-style diff format. It fetches law data from the e-Gov Law API v2 and computes structural diffs between different versions of laws, presenting changes in a familiar +/- format.

Related project: [open-gikai](../open-gikai/) — parliamentary proceeding viewer. Future integration planned (link amendments to the Diet sessions that discussed them).

## Tech Stack

- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS
- **Deployment**: Static Site Generation (SSG)
- **Data Pipeline**: Python 3.13+ scripts (managed with `uv`)
- **Data Source**: [e-Gov Law API v2](https://laws.e-gov.go.jp/api/2/) — point-in-time law text retrieval

## Development Commands

```bash
# Python pipeline
uv run python scripts/fetch.py <law_id> <date_before> <date_after>
uv run python scripts/diff.py <law_id> <date_before> <date_after>

# Frontend (in frontend/ directory)
cd frontend
npm run dev    # Development server
npm run build  # Static build
npm run lint   # Lint
```

## Project Structure

```
/
├── CLAUDE.md              This file
├── pyproject.toml         Python project config (uv)
├── scripts/               Python data pipeline
│   ├── fetch.py           Fetch law data from e-Gov API
│   ├── diff.py            Compute structural diff between law versions
│   └── requirements.txt   Python dependencies (legacy, use pyproject.toml)
├── data/                  Generated data (not committed)
│   ├── raw/               Raw API responses
│   └── diffs/             Computed diff JSON files
└── frontend/              Next.js application
    ├── app/               Pages and layouts
    ├── components/        React components
    ├── lib/               Types and data utilities
    └── public/data/       Static diff data for SSG
```

## Key Concepts

- **law_id**: e-Gov identifier (e.g., `129AC0000000089` = Civil Code)
- **asof**: Point-in-time parameter for the API — returns the law as enacted on that date
- **Article (条)**: Primary unit of comparison; diffs are computed per-article
- **Section path**: Hierarchical location (Part > Chapter > Section) of each article

## Git Conventions

- **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`
- **Branch strategy**: Direct to main for now; PRs for larger changes

## Coding Conventions

- TypeScript strict mode for frontend
- Code comments in English
- User-facing text in Japanese
- Tailwind CSS for styling
- Python: type hints, f-strings, pathlib for file paths

## Data Pipeline Flow

```
e-Gov API v2  →  fetch.py (raw JSON)  →  diff.py (structured diff)  →  frontend/public/data/
```

## API Notes

- e-Gov Law API v2 base URL: `https://laws.e-gov.go.jp/api/2`
- No authentication required
- Law text is structured XML represented as JSON (`tag`/`attr`/`children` tree)
- `GET /law_data/{law_id}?asof=YYYY-MM-DD` for point-in-time retrieval
- `GET /law_revisions/{law_id}` for amendment history
- Law texts are not copyrighted (Copyright Act Article 13)
