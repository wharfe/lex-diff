import { jpDate } from "./format";
import { LawDiffData, PendingInfo, PendingRevision, TimelineEntry } from "./types";

/*
 * Pending (not yet enforced) amendments — docs/pending-amendments/spec.md.
 *
 * "Not yet in force" changes with time, and a static page does not. So every
 * pending claim is dated by the day e-Gov was actually asked (generated_on):
 * "{date}時点で未施行" stays true after the date passes. The build date is not
 * such a day — nobody asked e-Gov then — so it never dates a claim about
 * e-Gov's record. A pending date may be a 政令 deadline rather than the day the
 * law takes effect, so a pending amendment is named by its law number, never
 * its year. Every pending wording on the site is in this file; components only
 * place it.
 */

/** JST calendar date of this build. Used only for date arithmetic. */
export const BUILD_DATE_JST: string = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Tokyo",
}).format(new Date());

export type PendingDiff = LawDiffData & { pending: PendingInfo };

/** Built by pending.py. Stays pending until the pipeline rebuilds it, even
 *  past its date: whether it took effect, and with what text, is unknown. */
export function isPendingDiff(d: LawDiffData): d is PendingDiff {
  return !!d.pending;
}

/** Past its date but never rebuilt. */
export function isOverduePending(d: PendingDiff): boolean {
  return d.date_after <= BUILD_DATE_JST;
}

export function asOfLabel(date: string): string {
  return `${date}時点で未施行`;
}

/** Name of a pending diff: its amending laws' numbers — facts, unlike a year. */
export function pendingName(d: PendingDiff): string {
  return d.pending.revisions
    .map((r) => r.amendment_law_num || r.amendment_law_title || r.law_revision_id)
    .join("／");
}

/** The date as e-Gov states it: its own wording when the date is not fixed.
 *  A bare date otherwise — whether a statute or a 政令 fixed it is not known. */
export function enforcementLabel(
  r: { enforcement_comment?: PendingRevision["enforcement_comment"] },
  date: string
): string {
  return r.enforcement_comment
    ? `${r.enforcement_comment}（e-Gov 上の予定日: ${date}）`
    : date;
}

export function enforcementLabels(d: PendingDiff): string {
  return d.pending.revisions
    .map((r) => enforcementLabel(r, d.date_after))
    .join("／");
}

/** The home row's date line. */
export function enforcementLinesFor(d: PendingDiff): string {
  return `施行日: ${enforcementLabels(d)}`;
}

export function enforcementLine(
  r: { enforcement_comment?: PendingRevision["enforcement_comment"] },
  date: string
): string {
  return `施行日: ${enforcementLabel(r, date)}`;
}

// --- Copy for the diff page -------------------------------------------------
// scripts/check_upcoming_page.py (check_diff_pages) rebuilds the title and
// description below from the data and compares them verbatim (#51).

const PLACES_SHOWN = 2;

/** Top-level headings (編 or 章) of the 本則 entries, most entries first, ties
 *  in order of first appearance. Facts from the diff — what a search reader
 *  wants from the title, without a model writing it. */
export function changedPlaces(d: PendingDiff): string[] {
  const counts = new Map<string, number>();
  for (const x of d.diffs) {
    const top = x.section_path?.[0];
    if (x.is_suppl || !top) continue;
    counts.set(top, (counts.get(top) ?? 0) + 1);
  }
  const order = [...counts.keys()];
  return [...order].sort(
    (a, b) => counts.get(b)! - counts.get(a)! || order.indexOf(a) - order.indexOf(b)
  );
}

/** 「第三章　事業者がとるべき措置等」 → 「事業者がとるべき措置等」. */
function headingName(heading: string): string {
  const i = heading.indexOf("\u3000");
  return i >= 0 ? heading.slice(i + 1) : heading;
}

function placesList(places: string[], show: (h: string) => string, sep: string): string {
  return (
    places.slice(0, PLACES_SHOWN).map(show).join(sep) +
    (places.length > PLACES_SHOWN ? "ほか" : "")
  );
}

/** The date only when e-Gov fixed it. A 政令 deadline may move (a 前倒し), and
 *  the page keeps its title after the day passes, so an unfixed one says
 *  未確定. A fixed date is e-Gov's record and stays a fact once passed —
 *  hence "施行日 {date}", not "{date}に施行" (no claim about the future). */
export function pendingTitle(d: PendingDiff): string {
  const when = isUnfixedPending(d) ? "施行日未確定" : `施行日 ${d.date_after}`;
  const main = d.diffs.filter((x) => !x.is_suppl).length;
  const places = changedPlaces(d);
  const gist =
    main > 0
      ? `本則${main}条` + (places.length > 0 ? `: ${placesList(places, headingName, "・")}` : "")
      : "附則のみの改正";
  return `${d.law_title}の改正【${when}】${gist}`;
}

/** Conditional, so true whenever (if ever) it takes effect; the 未施行 claim
 *  is dated by generated_on. */
export function pendingDescription(d: PendingDiff): string {
  const main = d.diffs.filter((x) => !x.is_suppl);
  const added = main.filter((x) => x.type === "added").length;
  const change =
    main.length > 0
      ? `施行されると本則${main.length}条が変わります${added > 0 ? `（うち新設${added}条）` : ""}。`
      : `施行されると附則${d.diffs.length}件が変わります（本則は変わりません）。`;
  const places = changedPlaces(d);
  const where = places.length > 0 ? `主な変更箇所: ${placesList(places, (h) => h, "、")}。` : "";
  return `${d.law_title}の改正（${pendingName(d)}）による新旧条文の差分。施行日: ${enforcementLabels(d)}。${change}${where}${asOfLabel(d.pending.generated_on)}。`;
}

export function pendingBreadcrumb(d: PendingDiff): string {
  return `${pendingName(d)}による改正（${asOfLabel(d.pending.generated_on)}）`;
}

export function pendingHeadline(d: PendingDiff): string {
  return `${asOfLabel(d.pending.generated_on)}の改正です。AIによる解説は付けていません。`;
}

export const PENDING_OVERDUE_NOTE =
  "e-Gov 上の予定日を過ぎていますが、このページはまだ作り直されていません。施行されたか・内容が変わったかは未確認です。";

/** What the "before" side is: dated by generated_on, each date as e-Gov states it. */
export function unenforcedBeforeNote(d: PendingDiff): string | null {
  const before = d.pending.unenforced_before;
  if (before.length === 0) return null;
  const list = before
    .map((u) => `${u.amendment_law_num || u.amendment_law_title}（施行日: ${enforcementLabel(u, u.enforcement_date)}）`)
    .join("、");
  return `改正直前の条文には、${asOfLabel(d.pending.generated_on)}の次の改正も反映されています（施行の順序は e-Gov 上の予定日による）: ${list}`;
}

export const PENDING_BEFORE_CHIP = "改正直前";
export const PENDING_AFTER_CHIP = "施行後（施行日は上記）";

export function pendingStatsLabel(total: number): string {
  return total > 0 ? `施行されると本則 ${total} 条が変わる` : "本則は変わらない";
}

export const PENDING_MAIN_SECTION_NOTE = "施行されると変わる条文";
export const PENDING_NO_MAIN_CHANGE = "この改正では本則の条文は変わりません（変更は附則のみ）。";

// --- Copy for the home page ---------------------------------------------------

export const PENDING_SECTION_TITLE = "施行予定の改正";
export const PENDING_SECTION_INTRO =
  "成立済みで、各行の日付の時点では未施行だった改正です。施行されると変わる条文を差分で確認できます（AIによる解説はありません）";

// --- Timeline -------------------------------------------------------------------

/** Diff ids built by pending.py, mapped to the date they were built. */
export type PendingGeneratedOn = ReadonlyMap<string, string>;

/** A timeline entry's pending badge, or null.
 *  - Linked to a pending diff: dated by that diff's generated_on.
 *  - Carries an 施行日 comment: no badge; its date line quotes e-Gov instead
 *    (the timeline does not record when e-Gov was asked).
 *  - A fixed date after this build: plain arithmetic, so dated by the build. */
export function entryPendingNote(
  e: TimelineEntry,
  generatedOn: PendingGeneratedOn
): string | null {
  const gen = e.diff_id ? generatedOn.get(e.diff_id) : undefined;
  if (gen) return asOfLabel(gen);
  if (e.enforcement_comment) return null;
  if (e.enforcement_date > BUILD_DATE_JST) return `${BUILD_DATE_JST}時点で施行日前`;
  return null;
}

/** Suffix after a timeline date that is e-Gov's scheduled one, not a fixed one. */
export function entryDateSuffix(e: TimelineEntry): string {
  return e.enforcement_comment ? "（予定日）" : "";
}

export function entryCommentLine(e: TimelineEntry): string | null {
  return e.enforcement_comment ? enforcementLine(e, e.enforcement_date) : null;
}

/** Whether an entry may stand for "the latest enforced amendment". */
export function isEnforcedEntry(
  e: TimelineEntry,
  generatedOn: PendingGeneratedOn
): boolean {
  return (
    !(e.diff_id && generatedOn.has(e.diff_id)) &&
    !e.enforcement_comment &&
    e.enforcement_date <= BUILD_DATE_JST
  );
}

/** The explainer's intro, written here rather than by the model: a model
 *  intro generalised past its items (「制度の仕組み自体は大きく変わらない」,
 *  #35). Items exclude 附則-only and table-changing amendments, so this says
 *  "選び", never "直近". */
export function explainerIntro(lawTitle: string, count: number): string {
  return `${lawTitle}の施行済みの改正から、法律の本文（本則）が変わった${count}回を選び、新しい順にまとめました。`;
}

export function explainerScopeNote(generatedOn: string): string {
  return `${jpDate(generatedOn)}時点で施行済みの改正が対象です。施行予定の改正は改正履歴をご覧ください。`;
}

// --- The /upcoming page (docs/upcoming-page/spec.md) ----------------------------
// scripts/check_upcoming_page.py compares the built page with these strings
// verbatim; change both together.

export const UPCOMING_TITLE = "施行予定の法改正一覧";
// No date, month or year: a static page keeps naming one after it has passed,
// and the nearest date may be a 政令 deadline (Gate 2 H2).
// "成立済みで施行日前" was an undated claim about the reader's present, and a
// search snippet outlives the date it describes (codex, Gate 3).
const UPCOMING_DESCRIPTION_HEAD =
  "e-Gov の記録で未施行だった法改正の一覧です（記録の日付は各行に表示）。";
const UPCOMING_DESCRIPTION_TAIL = "施行されると変わる条文を新旧の差分で確認できます。";
const UPCOMING_LAWS_SHOWN = 3;

/** Names the laws on the page (rows in page order, each law once) — what a
 *  search reader looks for — and still no date (#51). */
export function upcomingDescription(rows: { data: PendingDiff }[]): string {
  const laws = [...new Set(rows.map((r) => r.data.law_title))];
  const rest = laws.length - UPCOMING_LAWS_SHOWN;
  const named =
    laws.length > 0
      ? `${laws.slice(0, UPCOMING_LAWS_SHOWN).join("、")}${rest > 0 ? `ほか${rest}法令` : ""}の改正を載せています。`
      : "";
  return UPCOMING_DESCRIPTION_HEAD + named + UPCOMING_DESCRIPTION_TAIL;
}
export const UPCOMING_SCOPE =
  "lexdiff が収録する法令のうち、差分を作れた改正のみを載せています（e-Gov に施行日の記載がない改正や、条文中の表が変わる改正は載せていません）";
// Dated by each row: whether a date is fixed is e-Gov's record as of generated_on.
export const UPCOMING_UNFIXED_HEADING =
  "各行の日付の時点で、施行日が e-Gov 上で確定していなかった改正";
export const UPCOMING_EMPTY = "掲載できる施行予定の改正はありません";
export const UPCOMING_LINK_LABEL = "施行予定の改正をすべて見る →";

/** Not overdue pending diffs, by date then id: the home list's first rows
 *  and every row of /upcoming. */
export function upcomingPending<T extends { id: string; data: LawDiffData }>(
  all: T[]
): (T & { data: PendingDiff })[] {
  return all
    .flatMap((x) =>
      isPendingDiff(x.data) && !isOverduePending(x.data)
        ? [x as T & { data: PendingDiff }]
        : []
    )
    .sort((a, b) => byCodePoint(a.data.date_after, b.data.date_after) || byCodePoint(a.id, b.id));
}

/** Plain code-point order, as scripts/check_upcoming_page.py sorts: localeCompare
 *  collates, and could part from it on ties (Layer 3, Gate 3). */
function byCodePoint(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** /upcoming's sections: one per month of the fixed-date rows, ascending, then
 *  one for the rows whose date e-Gov did not fix. No empty section. */
export function groupUpcoming<T extends { id: string; data: PendingDiff }>(
  rows: T[]
): { key: string; heading: string; rows: T[] }[] {
  const months = new Map<string, T[]>();
  for (const r of rows.filter((r) => !isUnfixedPending(r.data))) {
    const m = upcomingMonth(r.data);
    months.set(m, [...(months.get(m) ?? []), r]);
  }
  const sections = [...months.keys()]
    .sort(byCodePoint)
    .map((m) => ({ key: m, heading: upcomingMonthHeading(m), rows: months.get(m)! }));
  const unfixed = rows.filter((r) => isUnfixedPending(r.data));
  if (unfixed.length > 0) {
    sections.push({ key: "unfixed", heading: UPCOMING_UNFIXED_HEADING, rows: unfixed });
  }
  return sections;
}

/** e-Gov records the date as a deadline or another law's start, not a day. */
export function isUnfixedPending(d: PendingDiff): boolean {
  return d.pending.revisions.some((r) => !!r.enforcement_comment);
}

/** "2026-12" from the date string itself, independent of any time zone. */
export function upcomingMonth(d: PendingDiff): string {
  return d.date_after.slice(0, 7);
}

/** Restates the recorded date; "…に施行" would assert a future event. */
export function upcomingMonthHeading(month: string): string {
  const [y, m] = month.split("-");
  return `施行日が${Number(y)}年${Number(m)}月の改正`;
}

/** The row's count is against a text that already holds earlier pending
 *  amendments (unenforcedBeforeNote) — said here, since the row is all a
 *  list reader sees (Gate 2 r2 M2). */
export function upcomingBeforeNote(d: PendingDiff): string | null {
  const n = d.pending.unenforced_before.length;
  // Dated, not "先に施行予定": unenforced_before can hold one already past its
  // date that e-Gov had not flipped (code-review, Gate 3).
  return n > 0
    ? `（${asOfLabel(d.pending.generated_on)}の他の改正 ${n} 件を反映した条文との比較）`
    : null;
}
