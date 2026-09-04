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
│   ├── llm.py             Shared Claude API helpers for the three scripts above
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
(key in `.env`) through the shared helpers in `llm.py`. All three are
hallucination-sensitive and are structured defensively; changes must preserve
that shape:

- Facts that must not be invented (enforcement year, whether a diff backs the
  entry, which articles changed) are computed in Python; the LLM only writes
  prose from the evidence it is handed.
- **Never call the model with an empty evidence list.** `annotate.py` raises
  instead. An amendment whose 本則 is untouched still has its 附則 as evidence —
  dropping it left the prompt empty and the model wrote from memory.
- The evidence excerpt must contain the change. `changed_excerpt()` centres on
  the SequenceMatcher opcodes; when it still has to trim, it says so in the
  prompt rather than claiming the excerpt is the whole of the evidence.
- A truncated answer is a failure, not a cheaper answer. `llm.response_text()`
  raises on `stop_reason == "max_tokens"`; storing the fragment as prose once
  shipped raw JSON to readers.
- Output is validated before it is written and before a cached entry is reused
  (`validate_annotation` / `validate_pr_summary` / `validate_explainer`);
  a failure exits non-zero and saves nothing.
- `explainer.py` additionally marks each amendment `grounded` (a diff exists →
  `why`/`impact` allowed) or ungrounded (only the amendment's name and year are
  known → prose stays within that, and `why`/`impact` are stripped).
- Annotations are cached by a fingerprint of model + prompt version + prompt
  text. Changing a prompt means bumping `PROMPT_VERSION` in `annotate.py`.

## Key Concepts

- **law_id**: e-Gov identifier (e.g., `129AC0000000089` = Civil Code)
- **asof**: Point-in-time parameter for the API — returns the law as enacted on that date
- **Article (条)**: Primary unit of comparison; diffs are computed per-article
- **Section path**: Hierarchical location (Part > Chapter > Section) of each article
- **本則 / 附則**: e-Gov numbers the 附則 (supplementary provisions) of each
  amending law from 1 independently of the main text, so a flat map keyed by
  article number lets 附則第一条 overwrite 本則第一条. `diff.py` therefore keys
  附則 as `suppl_<AmendLawNum>_<num>` (`suppl_key`), carries `is_suppl` and
  `amend_law_num` on every entry, and refuses a duplicate key rather than
  dropping an article. The frontend splits the two and counts only 本則 in every
  change count (`mainChangeCounts`). 附則 is not merely procedural — 労働基準法
  附則第138条 was the whole substance of its own amendment.

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
