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
uv run python scripts/timeline.py <law_id>     # Amendment history for /law/<law_id>
uv run python scripts/explainer.py <law_id>    # Plain-language "recent amendments" section
uv run pytest                                  # Python tests

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
│   ├── annotate.py        Per-article annotations
│   ├── timeline.py        Build amendment history for a law
│   ├── proposer.py        Bill sponsors/contributors via the NDL API
│   ├── enrich.py          Merge supplementary data into a diff
│   ├── law_summary.py     AI-generated law overview
│   ├── explainer.py       AI-generated "recent amendments" section (see below)
│   └── requirements.txt   Python dependencies (legacy, use pyproject.toml)
├── tests/                 pytest suite for the pure functions in scripts/
├── data/                  Generated data (not committed — all subdirs gitignored)
│   ├── raw/               Raw API responses
│   ├── diffs/             Computed diff JSON files
│   ├── timelines/         Amendment history per law
│   └── proposers/         Bill sponsor data from the NDL API
└── frontend/              Next.js application
    ├── app/               Pages and layouts
    ├── components/        React components
    ├── lib/               Types and data utilities
    └── public/data/       Static diff + timeline data for SSG (committed)
```

Scripts that write to `data/` also mirror their output into `frontend/public/data/`
when the destination file already exists — that mirrored copy is what ships.

## AI-Generated Content

`law_summary.py`, `annotate.py`, and `explainer.py` call the Claude API
(key in `.env`). `explainer.py` is the hallucination-sensitive one, so it is
structured defensively and changes should preserve that shape:

- Facts that must not be invented (enforcement year, whether a diff backs the
  entry) are computed in Python; the LLM only writes prose.
- Each amendment is `grounded` (a diff exists → `why`/`impact` allowed) or
  ungrounded (only the amendment's name and year are known → prose must stay
  within that, and `why`/`impact` are stripped).
- Output is validated before it is written; a failure exits non-zero and saves
  nothing. Pure functions are covered by `tests/test_explainer.py`.

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
