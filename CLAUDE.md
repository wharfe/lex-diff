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
uv run python scripts/law_summary.py <law_id>  # /law overview — fetches today's text itself
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
│   ├── lawtext.py         Reading the e-Gov law tree (shared by diff/law_summary)
│   └── requirements.txt   Python dependencies (legacy, use pyproject.toml)
├── tests/                 pytest suite — the pure functions in scripts/, plus
│                          test_shipped_data.py over frontend/public/data/
│                          (run in CI on every PR)
├── data/                  Generated data (not committed — all subdirs gitignored)
│   ├── raw/               Raw API responses
│   ├── diffs/             Computed diff JSON files
│   ├── timelines/         Amendment history per law
│   └── proposers/         Bill sponsor data from the NDL API
└── frontend/              Next.js application
    ├── app/               Pages and layouts
    ├── components/        React components
    ├── lib/               Types and data utilities, plus law-seo.ts — the one
    │                      place holding hand-written (not generated) copy
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
  (`validate_annotation` / `validate_pr_summary` / `validate_explainer` /
  `validate_summary`); a failure exits non-zero and saves nothing.
- `law_summary.py` builds its evidence from the law itself — the table of
  contents, every article caption, and article 1 in full (`build_evidence`).
  Article 1 is the purpose / scope clause, so it is the direct basis for the
  summary's `scope`. The whole text is never sent: 民法 is 226,000 characters.
  Its validation is in two layers because they can run in different places —
  `validate_summary_shape` (form + the abolished penalty names) needs no
  evidence and so also runs over shipped data in CI, while `validate_summary`
  adds the grounding rule: **every keyword must occur in the evidence**. Prose
  is not checked word by word (「事業者」「日常生活」 would be false positives);
  a keyword is a noun, so it can be. The penalty-name ban is deliberately
  scoped to `law_summary.py`: a diff's `pr_summary` legitimately says 懲役 when
  describing the amendment that renamed it.
- **The evidence has to be current, and `law_summary.py` fetches it itself** —
  in the same call as the generation, rather than reading `data/raw`. Deciding
  from disk whether the text was current was tried twice and failed twice, for
  one reason: nothing stored on disk records *when it was obtained*. Comparing
  against `<law_id>_revisions.json` trusted a second file whose own freshness
  nobody guarantees (`timeline.py` reuses an existing one indefinitely), and
  failed open when it was missing or malformed. Requiring the newest asof to be
  today's date only checked the filename — asof is the point in time being
  asked about, not the moment of asking, and
  `129AC0000000089_2026-04-01.json` was written on 2026-03-26. This mattered:
  10 of 12 laws were summarised from text older than their latest enforced
  revision, and every 刑法 snapshot predated the 2025-06-01 merger into 拘禁刑,
  so the prompt asked for current law while handing over repealed penalty names
  and banning their use in the same breath. A failed fetch raises rather than
  falling back to an older file, "today" is Asia/Tokyo (these are Japanese
  enforcement dates), and main() refuses to save if the JST date changed while
  the model was answering.
- `explainer.py` additionally marks each amendment `grounded` (a diff exists →
  `why`/`impact` allowed) or ungrounded (only the amendment's name and year are
  known → prose stays within that, and `why`/`impact` are stripped).
- Annotations are cached by a fingerprint of model + prompt version + prompt
  text. Changing a prompt means bumping `PROMPT_VERSION` in `annotate.py`.

Hand-written copy is the blind spot of all of the above: `frontend/lib/law-seo.ts`
supplies a page's `<title>` tail and meta description, and no validator sees it.
Its legal claims must be written from the article text in `frontend/public/data/`,
with the conditions intact — 「怠ると過料」 for 「正当な理由がないのに怠ったときは
十万円以下の過料」 is the same class of error as an abolished penalty name. Facts
the page already computes (the amendment count) belong in the template, not in
the prose. `assertLawSeoOverridesValid` fails the build on an unknown law id or a
blank field, because a typo would silently revert a page that took months to rank.

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
  dropping an article. Every change count is 本則-only, on both sides: the
  frontend's `mainChangeCounts` and the published JSON's
  `stats.added/modified/deleted` (`compute_stats` in `diff.py`; `stats.suppl` is
  how many 附則 entries there are, and a per-type breakdown of them is
  deliberately not published). 附則 is not merely procedural — 労働基準法
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
