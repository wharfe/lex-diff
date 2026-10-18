"""Generate a plain-language 'recent amendments' explainer for a law using Claude AI.

Usage:
    python scripts/explainer.py <law_id>

Example:
    python scripts/explainer.py 416AC0000000123
"""

import sys
import json
import os
import re
import unicodedata
from typing import Callable
import anthropic
from llm import response_text, strip_code_fence
from pending import today_jst
import diff
from pathlib import Path

MODEL = "claude-sonnet-5"
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend" / "public" / "data"
MAX_CHANGES = 4


def is_pending_entry(entry: dict, today: str, pending_ids: frozenset[str]) -> bool:
    """Not yet enforced, as far as anything on disk can tell.

    A 施行日 comment exists only while the date is not fixed (never on an
    enforced revision), and a diff built by pending.py stays pending until the
    pipeline rebuilds it — past its date it may still be e-Gov's
    pre-enforcement text, or the date may have been a 政令 deadline.
    """
    return (
        (entry.get("enforcement_date") or "") > today
        or bool(entry.get("enforcement_comment"))
        or entry.get("diff_id") in pending_ids
    )


def select_changes(
    timeline: list[dict],
    today: str,
    pending_ids: frozenset[str],
    load: Callable[[str], dict | None],
    has_table_change: Callable[[str], bool],
) -> list[dict]:
    """Deterministically select up to MAX_CHANGES items, newest first.

    An item is one enforced diff whose 本則 changed (docs/issue-35/spec.md),
    never one amending law. Matching laws by title folded distinct laws that
    share one (令和2年 and 令和7年 公益通報者保護法 amendments), and an amending
    law could only be grounded by one of its stages: a 附則-only stage went to
    the model as "本則は変わらない" while the 本則 itself was still pending.
    A diff states what changed on its own day and nothing more.

    Skipped: entries without a diff, pending entries and pending.py diffs (they
    ground nothing), diffs with no 本則 change, and diffs whose tables changed
    (a table change is invisible to diff.py, #28). A diff that cannot be read
    or carries no pr_summary stops the run rather than silently vanishing.
    """
    names: dict[str, list[str]] = {}
    dates: dict[str, str] = {}
    pending: set[str] = set()
    for entry in timeline:
        diff_id = entry.get("diff_id")
        if not diff_id:
            continue
        dates[diff_id] = entry.get("enforcement_date") or ""
        if entry.get("amendment_law_title"):
            names.setdefault(diff_id, []).append(entry["amendment_law_title"])
        if is_pending_entry(entry, today, pending_ids):
            pending.add(diff_id)

    changes: list[dict] = []
    for diff_id in sorted(dates, key=lambda d: dates[d], reverse=True):
        if diff_id in pending:
            continue
        diff = load(diff_id)
        if diff is None:
            raise ValueError(f"{diff_id}: linked from the timeline but cannot be read")
        if "pending" in diff or diff["stats"]["main"] == 0 or has_table_change(diff_id):
            continue
        change = {
            "year": dates[diff_id][:4],
            "enforcement_date": dates[diff_id],
            "diff_id": diff_id,
            "source_title": (names.get(diff_id) or [""])[0],
            "grounded": True,
        }
        changes.append(apply_diff(change, diff, names.get(diff_id, [])))
        if len(changes) == MAX_CHANGES:
            break
    return changes


# A claim that something will take effect. Pending amendments are never given
# to the model, so any such claim has no evidence behind it; the old prompt let
# it write 「2028年に施行される予定」 and 「施行日は政令で定められます」.
FUTURE_WORDS = ("予定", "見込")
_KANJI_DIGITS = {c: i for i, c in enumerate("〇一二三四五六七八九")}


def _kanji_number(text: str) -> int | None:
    """一 .. 九十九, enough for a 令和 year."""
    if text == "元":
        return 1
    if "十" in text:
        tens, _, ones = text.partition("十")
        value = (_KANJI_DIGITS.get(tens, -1) if tens else 1) * 10
        value += _KANJI_DIGITS.get(ones, -1) if ones else 0
    else:
        value = _KANJI_DIGITS.get(text, -1) if len(text) == 1 else -1
    return value if value > 0 else None


def mentioned_years(text: str) -> list[int]:
    """Western years in 西暦 and 令和 notation (Arabic or kanji), after NFKC."""
    text = unicodedata.normalize("NFKC", text)
    years = [int(y) for y in re.findall(r"(\d{4})年", text)]
    years += [2018 + int(n) for n in re.findall(r"令和(\d{1,2})年", text)]
    for n in re.findall(r"令和([元〇一二三四五六七八九十]{1,3})年", text):
        value = _kanji_number(n)
        if value is not None:
            years.append(2018 + value)
    return years


def _texts(explainer: dict) -> list[str]:
    out = []
    for c in explainer.get("recent_changes") or []:
        if isinstance(c, dict):
            out += [c.get(k) or "" for k in ("title", "what", "why", "impact")]
    return [t for t in out if isinstance(t, str)]


def validate_explainer_shape(explainer: dict) -> list[str]:
    """Checks that need no evidence, so they also run over shipped data in CI."""
    errors: list[str] = []
    # No intro or faq: written over the whole law, they generalised past the
    # items they were given (「制度の仕組み自体は大きく変わらない」, #35).
    # The page writes its own intro from these facts.
    for key in ("generated_on", "recent_changes"):
        if key not in explainer:
            errors.append(f"missing key: {key}")
    if errors:
        return errors

    gen = explainer["generated_on"]
    if not isinstance(gen, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", gen):
        return ["generated_on must be YYYY-MM-DD"]

    rc = explainer["recent_changes"]
    if not isinstance(rc, list) or not (1 <= len(rc) <= MAX_CHANGES):
        errors.append(f"recent_changes count out of range (1-{MAX_CHANGES})")
    else:
        seen: set[str] = set()
        for i, c in enumerate(rc):
            if not isinstance(c, dict):
                errors.append(f"recent_changes[{i}] not an object")
                continue
            for k in ("diff_id", "enforcement_date", "year", "title", "what"):
                if not c.get(k):
                    errors.append(f"recent_changes[{i}] missing {k}")
            if c.get("year") != (c.get("enforcement_date") or "")[:4]:
                errors.append(f"recent_changes[{i}] year disagrees with enforcement_date")
            what = c.get("what", "")
            if not isinstance(what, str) or not (0 < len(what) <= 120):
                errors.append(f"recent_changes[{i}] what length out of range")
            if c.get("diff_id") in seen:
                errors.append(f"recent_changes[{i}] duplicate diff_id {c.get('diff_id')}")
            seen.add(c.get("diff_id"))

    gen_year = int(gen[:4])
    for text in _texts(explainer):
        normalized = unicodedata.normalize("NFKC", text)
        for word in FUTURE_WORDS:
            if word in normalized:
                errors.append(f"claims the future ({word}): {text[:40]}")
        if any(y > gen_year for y in mentioned_years(text)):
            errors.append(f"names a year after {gen_year}: {text[:40]}")
    return errors


def validate_explainer(explainer: dict, selected: list[dict], raw: dict) -> list[str]:
    """Shape, plus agreement with the selection it was generated from."""
    errors = validate_explainer_shape(explainer)
    rc = explainer.get("recent_changes")
    if isinstance(rc, list) and len(rc) != len(selected):
        # normalize zips by position: a dropped item would hand the next
        # item's prose this one's diff_id and date.
        errors.append(f"recent_changes count {len(rc)} != selected {len(selected)}")
    items = raw.get("recent_changes")
    if not isinstance(items, list) or len(items) != len(selected):
        # Counted before normalize: zip() cuts surplus items off, so an extra
        # item would leave the counts agreeing with every fact shifted.
        n = len(items) if isinstance(items, list) else "no list"
        errors.append(f"model returned count {n} != selected {len(selected)}")
    if isinstance(rc, list):
        for i, (sel, c) in enumerate(zip(selected, rc)):
            if not isinstance(c, dict):
                continue
            # A fine's condition is part of the rule: 「怠ると過料」 for 「正当な
            # 理由がないのに…怠ったときは…過料」 is wrong (CLAUDE.md, law-seo.ts).
            evidence = json.dumps(sel.get("pr_summary") or {}, ensure_ascii=False)
            text = "".join(c.get(k) or "" for k in ("title", "what", "why", "impact"))
            if "正当な理由" in evidence and "過料" in text and "正当な理由" not in text:
                errors.append(f"recent_changes[{i}] names a fine without its 正当な理由 condition")
    return errors


def normalize_explainer(raw: dict, selected: list[dict], generated_on: str) -> dict:
    """Attach the deterministic facts from `selected` to the LLM's prose."""
    changes = []
    items = raw.get("recent_changes") or []
    if not isinstance(items, list):
        items = []
    for sel, item in zip(selected, items):
        if not isinstance(item, dict):
            continue
        change = {
            "year": sel["year"],
            "enforcement_date": sel["enforcement_date"],
            "diff_id": sel["diff_id"],
            "title": (item.get("title") or sel["source_title"]).strip(),
            "what": (item.get("what") or "").strip(),
            "grounded": True,
        }
        for key in ("why", "impact"):
            value = (item.get(key) or "").strip()
            if value:
                change[key] = value
        changes.append(change)
    return {"generated_on": generated_on, "recent_changes": changes}


def load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def shipped_pending_ids() -> frozenset[str]:
    """Shipped diffs built by pending.py (they carry a `pending` block)."""
    ids = set()
    for path in FRONTEND_DIR.glob("*_*_*.json"):
        if "pending" in json.loads(path.read_text()):
            ids.add(path.stem)
    return frozenset(ids)


def load_diff(diff_id: str) -> dict | None:
    """Load a diff by id from the frontend data dir or data/diffs."""
    for base in (FRONTEND_DIR, DATA_DIR / "diffs"):
        path = base / f"{diff_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    return None


def apply_diff(change: dict, diff: dict | None, same_day_titles: list[str] | None = None) -> dict:
    """Ground a selected change in its diff, and name it as the diff does.

    A timeline entry names one law, but a diff can carry several laws enforced on the same day (刑法 2025-06-01). The
    diff's own title names all of them, so it is the one to show (#23). A diff
    published before titles were collected names one law however many took
    effect that day, so the timeline's entries linking this same diff
    (same_day_titles) decide too — never every entry of that date, which can
    include a pending one.
    """
    pr_summary = (diff or {}).get("pr_summary")
    if not pr_summary:
        # An item exists only because its diff grounds it; there is no
        # ungrounded fallback any more (docs/issue-35/spec.md).
        raise ValueError(f"{change.get('diff_id')}: diff has no pr_summary")
    change["pr_summary"] = pr_summary
    after = diff.get("revision_after", {})
    titles = after.get("amendment_law_titles") or []
    if len(titles) < 2 and len(same_day_titles or []) > 1:
        titles = list(same_day_titles)
    change["multi_law"] = len(titles) > 1
    title = (
        "／".join(titles) if change["multi_law"]
        else after.get("amendment_law_title") or change["source_title"]
    )
    # e-Gov marks a partial promulgation 「…　抄」 on some entries only.
    change["source_title"] = title.removesuffix("　抄")
    return change


def build_prompt(law_title, law_num, category, summary_desc, changes):
    lines = []
    for i, c in enumerate(changes):
        pr = c.get("pr_summary") or {}
        block = [
            f"[改正{i + 1}] {c['enforcement_date']}の施行分 / 改正法: {c['source_title']}",
            "  この日に施行された変更の差分要約。what/why/impactはこれに基づいて書く:",
            f"    タイトル: {pr.get('title', '')}",
            f"    概要: {pr.get('summary', '')}",
            f"    背景: {pr.get('background', '')}",
            f"    影響: {pr.get('impact', '')}",
        ]
        if c.get("multi_law"):
            block.append("  この差分には同じ日に施行された複数の法令の変更が含まれる。"
                         "どの変更がどの法令によるものかは分からないので、"
                         "個々の変更を特定の法令に帰属させないこと。")
        lines.append("\n".join(block))
    changes_text = "\n\n".join(lines)

    return f"""あなたは日本の法律をわかりやすく解説する専門家です。以下の法律の「最近の改正」を、一般市民向けにJSON形式で解説してください。

法令名: {law_title}
法令番号: {law_num}
分類: {category}
法律の概要: {summary_desc}

最近の施行（この{len(changes)}件についてのみ書く。順番・件数を変えない）:
{changes_text}

出力JSON形式:
{{
  "recent_changes": [
    {{"title": "変更の通称（例: 相続登記の義務化）", "what": "何が変わったか（40-100字）", "why": "なぜ変わったか（40-100字）", "impact": "私たちへの影響（40-100字）"}}
  ]
}}

ルール:
- recent_changes は入力の改正と同じ順番・同じ件数で出力する。
- 各項目は、その日に施行された変更だけを書く。改正法全体について述べない。
- 入力に無い改正や変更について、あるとも無いとも書かない。法律全体についての一般化（「制度自体は変わらない」など）を書かない。
- まだ施行されていない改正や、これからの施行について書かない。「予定」「見込」という語を使わない。
- 差分要約にある将来の表現（今後・政令で定める日から施行 など）を写さない。附則の施行期日の定めから、その改正が未施行だと推測しない。
- 提供情報に無い事実（数値・期限・因果）を断定しない。不確実なら書かない。
- 罰則（罰金・拘禁刑）と行政処分（勧告・命令・業務改善命令など）を混同しない。罰金を「行政処分」と書かない。
- JSONのみを出力する。"""


def generate_explainer(law_title, law_num, category, summary_desc, changes) -> dict:
    client = anthropic.Anthropic()
    prompt = build_prompt(law_title, law_num, category, summary_desc, changes)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response_text(response)
    text = strip_code_fence(text)
    return json.loads(text)


def raw_tables_changed(diff_id: str) -> bool:
    """diff.tables_changed on the raw snapshots the diff was built from.

    Diffs shipped before that check existed never ran it (#35 Gate 2 r3).
    Missing raw text stops the run: an unchecked diff is not evidence.
    """
    law_id, before, after = diff_id.split("_")
    trees = []
    for date in (before, after):
        path = DATA_DIR / "raw" / f"{law_id}_{date}.json"
        if not path.exists():
            raise FileNotFoundError(f"{path}: run fetch.py {law_id} {before} {after}")
        trees.append(json.loads(path.read_text())["law_full_text"])
    return diff.tables_changed(*trees)


def save_timeline(law_id: str, timeline: dict, timeline_path: Path) -> None:
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    frontend_path = FRONTEND_DIR / "timelines" / f"{law_id}.json"
    if frontend_path.exists():
        frontend_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    load_env()
    law_id = sys.argv[1]

    timeline_path = DATA_DIR / "timelines" / f"{law_id}.json"
    if not timeline_path.exists():
        print(f"Error: Run timeline.py first for {law_id}")
        sys.exit(1)
    timeline = json.loads(timeline_path.read_text())

    today = today_jst()
    changes = select_changes(
        timeline["timeline"], today, shipped_pending_ids(), load_diff,
        lambda d: d in diff.SHIPPED_WITH_TABLE_CHANGES or raw_tables_changed(d),
    )
    if not changes:
        # No enforced 本則 change to write from: the page shows no explainer
        # rather than one written from names and years alone.
        timeline.pop("explainer", None)
        save_timeline(law_id, timeline, timeline_path)
        print(f"{timeline['law_title']}: no enforced diff with a 本則 change; explainer removed")
        return

    print(f"Generating explainer for {timeline['law_title']} ({len(changes)} changes)...")
    raw = generate_explainer(
        timeline["law_title"],
        timeline["law_num"],
        timeline.get("category", ""),
        (timeline.get("summary") or {}).get("description", ""),
        changes,
    )
    explainer = normalize_explainer(raw, changes, today)

    errors = validate_explainer(explainer, changes, raw)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        print("\nGenerated (not saved):")
        print(json.dumps(explainer, ensure_ascii=False, indent=2))
        sys.exit(2)
    if today_jst() != today:
        # generated_on dates the selection; a date change while the model
        # answered would make it name a day the selection did not see.
        print(f"The JST date changed during generation ({today}); not saving. Re-run.")
        sys.exit(3)

    timeline["explainer"] = explainer
    save_timeline(law_id, timeline, timeline_path)

    for c in explainer["recent_changes"]:
        print(f"  {c['enforcement_date']} {c['title']}")
    print(f"  Saved: {timeline_path}")


if __name__ == "__main__":
    main()
