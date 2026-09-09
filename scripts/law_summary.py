"""Generate a brief summary for a law from the law's own text.

Usage:
    python scripts/law_summary.py <law_id>

Example:
    python scripts/law_summary.py 129AC0000000089

The model is handed evidence built out of the law itself — its table of
contents, every article caption, and article 1 in full (build_evidence). It
used to be handed nothing but the law's name, number, category and revision
count, so every word of the answer came out of its own memory; that is issue
#16, and this script is the last of the three generators to leave it.

Two guards, in different places, because they can run in different places:

- validate_summary_shape() checks form and the abolished penalty names. It
  needs no evidence, so it also runs over already-shipped data in CI.
- validate_summary() adds the grounding rule — every keyword must occur in the
  evidence. That needs the law text, which only exists at generation time
  (data/raw is gitignored).

Neither can judge prose. A description that invents a requirement still passes;
what the evidence buys is that the model has no reason to invent one.

The evidence must also be *current*. data/raw holds whatever dates someone
fetched for a diff, which is unrelated to "now": every snapshot of 刑法 here
predated the 2025-06-01 merger of 懲役/禁錮 into 拘禁刑, so the prompt asked for
a description of current law while handing over repealed penalty names and
banning their use in the same breath. main() now refuses to run when the newest
snapshot is older than the law's latest enforced revision.
"""

import sys
import json
import os
import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import anthropic
from llm import complete_json
from lawtext import extract_text, walk_tags
from fetch import fetch_law_data

MODEL = "claude-sonnet-5"
DATA_DIR = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"

# Penalty names abolished on 2025-06-01, when 懲役 and 禁錮 were merged into
# 拘禁刑. A law summary describes the law as it stands now, so these words can
# never be right here — unlike a diff's pr_summary, which legitimately says
# "懲役 was renamed to 拘禁刑" about the amendment that did the renaming.
#
# 禁固 and 禁こ are the newspaper spellings of 禁錮; a model reaches for them as
# readily as for the 常用漢字 form, and a ban that lists only 禁錮 would let the
# same mistake through one character later.
#
# This is deliberately context-blind, and that costs something: a summary that
# says, correctly, "懲役 and 禁錮 were merged into 拘禁刑 in 2025" is rejected too.
# That is the safe direction to fail — the script exits without saving and the
# next run rewrites the sentence, whereas the other direction publishes an
# abolished penalty as current law, which is the bug this exists for.
ABOLISHED_PENALTY_TERMS = ("懲役", "禁錮", "禁固", "禁こ")

MAX_KEYWORDS = 5
MIN_KEYWORD_LEN = 2

# Enforcement dates are Japanese calendar dates, so "today" is Tokyo's. On a
# UTC runner every Japanese midnight-to-09:00 would otherwise be yesterday.
JST = ZoneInfo("Asia/Tokyo")


# Headings that make up a law's table of contents, outermost first.
STRUCTURE_TITLE_TAGS = {"PartTitle", "ChapterTitle", "SectionTitle", "SubsectionTitle"}

# Subtrees the evidence stops at. 附則 is a different axis from the main text
# and says nothing about what the law is for. TOC is the law's own table of
# contents element, which repeats every Part/Chapter/Section title that also
# appears in the body — collecting both printed the whole outline twice (民法:
# 364 heading lines of which 197 were duplicates).
SKIP_SUBTREES = {"SupplProvision", "TOC"}


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def build_evidence(law_full_text: dict) -> str:
    """The law's own text, cut down to what a summary can be written from.

    Three things, and deliberately not the whole law: 民法 is 226,000
    characters and does not fit in a prompt at any useful price.

    - the table of contents, which is the law's own account of its shape
    - every article caption, which together are the list of what it covers
      (1,090 of them in 民法, 15,467 characters — dense and cheap)
    - article 1 in full, which is the purpose / scope clause and so the direct
      basis for the summary's `scope` field. 刑法第一条 reads "日本国内において
      罪を犯したすべての者に適用する" — that *is* the answer, verbatim.

    Raises rather than returning something empty: calling the model with no
    evidence is what let it write from memory in the first place. The emptiness
    test is on the assembled text, not on the node lists — a heading node whose
    text is blank makes the list truthy while contributing nothing, so testing
    the lists sent "## 目次" alone to the model and called that evidence.
    """
    headings = [
        t for t in (
            extract_text(n).strip()
            for n in walk_tags(law_full_text, STRUCTURE_TITLE_TAGS, stop_at=SKIP_SUBTREES)
        ) if t
    ]
    captions = [
        t for t in (
            extract_text(n).strip()
            for n in walk_tags(law_full_text, {"ArticleCaption"}, stop_at=SKIP_SUBTREES)
        ) if t
    ]
    articles = walk_tags(law_full_text, {"Article"}, stop_at=SKIP_SUBTREES)
    # An Article carrying only its own title yields "第一条" — a label, not
    # text. extract_text cannot tell the two apart, so the test is structural:
    # the article must contain a sentence, and that sentence must have words in
    # it. A present-but-empty <Sentence/> is what a truncated API response
    # looks like, and it passed a check for the tag alone.
    first_article = ""
    if articles and any(
        extract_text(n).strip() for n in walk_tags(articles[0], {"Sentence"})
    ):
        first_article = extract_text(articles[0]).strip()
    # Do not call it 第一条 without checking. articles[0] is only the first in
    # document order; a law whose 第一条 was 削除 and dropped from the tree would
    # have its 第一条の二 handed over under a label asserting otherwise, and the
    # prompt tells the model this article is where `scope` comes from.
    first_num = articles[0].get("attr", {}).get("Num", "") if articles else ""

    parts = []
    if headings:
        parts.append("## 目次\n" + "\n".join(headings))
    if captions:
        parts.append("## 各条の見出し\n" + "\n".join(captions))
    if first_article:
        if first_num == "1":
            parts.append("## 第一条（全文）\n" + first_article)
        else:
            # The design leans on article 1 being the purpose / scope clause.
            # When there is no article 1, say so rather than letting the model
            # read a definition or duty clause as if it stated the scope.
            parts.append(
                f"## 最初の条（第{first_num}条・全文）\n"
                "※この法令には第一条が無いため、目的・適用範囲を述べた条ではない"
                "可能性がある。適用範囲は断定せず、目次と見出しから言える範囲に"
                "とどめること。\n" + first_article
            )

    evidence = "\n\n".join(parts)
    # Section labels alone are not evidence; measure what is under them.
    body = evidence.replace("## 目次", "").replace("## 各条の見出し", "")
    if not body.strip() or not (headings or captions or first_article):
        raise ValueError(
            "no law text to summarise — refusing to call the model with empty "
            "evidence (it would answer from memory)"
        )
    return evidence


def fetch_evidence(raw_dir: Path, law_id: str, today: str) -> str:
    """Fetch the law as it stands today and build the evidence from it.

    The fetch is here, in the same call as the generation, on purpose. Reading
    whatever happened to be in data/raw was tried twice and failed twice, for
    the same reason both times: nothing on disk says when it was obtained.

    - Comparing the snapshot against <law_id>_revisions.json trusted a second
      file whose own freshness nobody guaranteed, and failed open when it was
      missing, malformed or empty.
    - Requiring the newest asof to be today's date only checked the *filename*.
      asof is the point in time being asked about, not when the answer was
      obtained: 129AC0000000089_2026-04-01.json was written on 2026-03-26, and
      would have passed as "today's" on April 1st.

    Fetching immediately before the call removes the question rather than
    answering it. A failed fetch raises; there is no fall-back to an older
    file, because an older file is exactly the thing that caused this.
    """
    doc = fetch_law_data(law_id, today)
    if not isinstance(doc, dict) or not doc.get("law_full_text"):
        raise ValueError(
            f"the API returned no law_full_text for {law_id} asof {today}"
        )
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{law_id}_{today}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2)
    )
    return build_evidence(doc["law_full_text"])


def validate_summary_shape(summary: dict) -> list[str]:
    """The checks that can be made without the law text in hand.

    Split out from validate_summary because the two run in different places.
    A shipped summary is checked long after generation, from a repository that
    does not carry data/raw (it is gitignored, so CI has no snapshots at all);
    all that can be asked of it there is that it is well formed and free of the
    abolished penalty names. Grounding needs the evidence and so belongs to
    generation time only — see validate_summary below.
    """
    errors: list[str] = []
    if not isinstance(summary, dict):
        return ["summary is not an object"]
    for key in ("description", "scope", "keywords"):
        if key not in summary:
            errors.append(f"missing key: {key}")
    if errors:
        return errors

    description = summary["description"]
    if not isinstance(description, str) or not (40 <= len(description) <= 400):
        errors.append("description length out of range (40-400)")

    scope = summary["scope"]
    if not isinstance(scope, str) or not (5 <= len(scope) <= 200):
        errors.append("scope length out of range (5-200)")

    keywords = summary["keywords"]
    if not isinstance(keywords, list) or not (1 <= len(keywords) <= MAX_KEYWORDS):
        errors.append(f"keywords count out of range (1-{MAX_KEYWORDS})")
    elif not all(isinstance(k, str) and k.strip() for k in keywords):
        errors.append("keywords must all be non-empty strings")
    else:
        # Output quality, not grounding. The containment check cannot reject a
        # single character — 「刑」 occurs inside 「刑罰」, so any kanji the law
        # uses at all passes it, and 刑法 shipped exactly that as a keyword.
        # This length rule does not make a keyword meaningful either (「の罪」
        # would pass); it removes the one failure that was actually observed.
        for k in keywords:
            if len(k.strip()) < MIN_KEYWORD_LEN:
                errors.append(
                    f"keyword too short to be a term: {k}"
                    f" (need {MIN_KEYWORD_LEN}+ characters)"
                )

    blob = json.dumps(summary, ensure_ascii=False)
    for term in ABOLISHED_PENALTY_TERMS:
        if term in blob:
            errors.append(
                f"abolished penalty name in summary: {term}"
                " (懲役・禁錮 were merged into 拘禁刑 on 2025-06-01)"
            )
    return errors


def validate_summary(summary: dict, evidence: str) -> list[str]:
    """Shape, plus: every keyword must actually occur in the law's own text.

    `evidence` is required rather than optional so that a caller which lost it
    fails loudly instead of quietly falling back to the memory-only behaviour
    this function exists to end.

    A keyword is a noun: either the law contains the word or it does not. Prose
    cannot be checked this way — a summary may fairly say 事業者 or 日常生活
    without the statute using either word — but an invented institution almost
    always surfaces in the keywords first, and catching it there costs nothing.
    """
    if not evidence or not evidence.strip():
        return ["evidence is empty — refusing to validate a summary with no basis"]

    errors = validate_summary_shape(summary)
    keywords = summary.get("keywords") if isinstance(summary, dict) else None
    if isinstance(keywords, list):
        for kw in keywords:
            if isinstance(kw, str) and kw.strip() and kw.strip() not in evidence:
                errors.append(
                    f"keyword not found in the law text: {kw}"
                    " (keywords must come from the law's own headings or article 1)"
                )
    return errors


def generate_summary(
    law_title: str,
    law_num: str,
    category: str,
    revision_count: int,
    evidence: str,
) -> dict:
    """Generate a brief plain-language summary of a law from its own text."""
    client = anthropic.Anthropic()

    prompt = f"""あなたは日本の法律の専門家です。以下の法律について、一般市民向けの簡潔な説明をJSON形式で出力してください。

法令名: {law_title}
法令番号: {law_num}
分類: {category}
改正回数: {revision_count}回

--- 以下はこの法律の実際の条文から機械的に抜き出した根拠です ---

{evidence}

--- 根拠ここまで ---

制約:
- 上の根拠に書かれていることだけを使って書いてください。根拠に無い制度・用語・数値を補わないでください。
- keywords は必ず根拠テキストに現れる語から選んでください（現れない語は機械的に弾かれ、やり直しになります）。
- keywords は2文字以上の意味のある用語にしてください（「刑」のような一文字は弾かれます）。
- 根拠は目次・各条の見出し・第一条だけで、条文本文の大部分は含まれていません。書かれていない細部を推測で埋めないでください。
- 2025年6月1日施行の改正刑法により「懲役」「禁錮」は「拘禁刑」に一本化されました。現行制度の説明にこれらの刑名を使わないでください。
- 現在の制度として言えることだけを書き、廃止された制度名・過去の呼称を現行のものとして提示しないでください。

以下のJSON形式で出力してください：

{{
  "description": "この法律が何を定めているかを2-3文で（専門用語を避け、日常生活との関わりを含めて）",
  "scope": "この法律の適用範囲を1文で（例：すべての国民、事業者、特定の業種など）",
  "keywords": ["関連キーワード", "最大5つ"]
}}

JSONのみを出力してください。"""

    return complete_json(client, MODEL, prompt, max_tokens=4000)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    load_env()
    law_id = sys.argv[1]

    # Load timeline data
    timeline_path = DATA_DIR / "timelines" / f"{law_id}.json"
    if not timeline_path.exists():
        print(f"Error: Run timeline.py first for {law_id}")
        sys.exit(1)

    timeline = json.loads(timeline_path.read_text())

    # Get category from revision data
    rev_path = DATA_DIR / "raw" / f"{law_id}_revisions.json"
    category = ""
    if rev_path.exists():
        rev_data = json.loads(rev_path.read_text())
        if rev_data.get("revisions"):
            category = rev_data["revisions"][0].get("category", "")

    # The law's own text, as it stands right now: fetched in this call rather
    # than read off disk, because nothing on disk records when it was obtained.
    raw_dir = DATA_DIR / "raw"
    today = datetime.datetime.now(JST).date().isoformat()
    evidence = fetch_evidence(raw_dir, law_id, today)

    print(f"Generating summary for {timeline['law_title']}...")
    print(f"  Evidence: {len(evidence)} chars from the law text")
    summary = generate_summary(
        timeline["law_title"],
        timeline["law_num"],
        category,
        timeline["revision_count"],
        evidence,
    )

    errors = validate_summary(summary, evidence)
    if errors:
        print("Validation failed — nothing was saved:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(2)

    print(f"  Description: {summary['description'][:80]}...")

    # Extract unique contributors from timeline
    contributors = {}
    for entry in timeline.get("timeline", []):
        proposer = entry.get("proposer")
        if proposer and proposer.get("minister") and proposer["minister"].get("name"):
            minister = proposer["minister"]
            name = minister["name"]
            if name not in contributors:
                contributors[name] = {
                    "name": name,
                    "position": minister.get("position", ""),
                    "party": minister.get("party"),
                    "count": 0,
                }
            contributors[name]["count"] += 1

    # Sort by count descending
    contributor_list = sorted(contributors.values(), key=lambda x: x["count"], reverse=True)

    # The generation takes long enough to cross midnight. A summary written
    # from yesterday's text and saved today would claim to describe current law
    # on a day an amendment may have come into force.
    if datetime.datetime.now(JST).date().isoformat() != today:
        print(
            f"The JST date changed during generation ({today} -> "
            f"{datetime.datetime.now(JST).date().isoformat()}); not saving. "
            "Re-run to fetch today's text."
        )
        sys.exit(3)

    # Update timeline data
    timeline["summary"] = summary
    timeline["category"] = category
    timeline["contributors"] = contributor_list

    # Save
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))

    # Update frontend
    frontend_path = FRONTEND_DIR / "timelines" / f"{law_id}.json"
    if frontend_path.exists():
        frontend_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))

    print(f"  Contributors: {len(contributor_list)}")
    print(f"  Saved: {timeline_path}")


if __name__ == "__main__":
    main()
