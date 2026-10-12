import { LawDiffData, PendingInfo, PendingRevision, TimelineEntry } from "./types";

/*
 * Pending (not yet enforced) amendments — docs/pending-amendments/spec.md.
 *
 * "Not yet in force" changes with time, and a static page does not. So no
 * pending claim is written in the present tense: each is dated ("{date}時点で
 * 未施行"), which stays true after the date passes. A pending date may be a
 * 政令 deadline rather than the day the law takes effect, so the year is never
 * used to name a pending amendment; its law number is. Every pending wording
 * on the site comes from this file.
 */

/** JST calendar date of this build. */
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

/** The date as e-Gov states it: its own wording when not fixed. */
export function enforcementLabel(
  r: Pick<PendingRevision, "enforcement_comment">,
  date: string
): string {
  return r.enforcement_comment
    ? `${r.enforcement_comment}（e-Gov 上の予定日: ${date}）`
    : `${date}（法律で定められた施行日）`;
}

/** Diff ids built by pending.py, mapped to the date they were built. */
export function pendingGeneratedOn(
  diffs: { id: string; data: LawDiffData }[]
): Map<string, string> {
  const out = new Map<string, string>();
  for (const { id, data } of diffs) {
    if (isPendingDiff(data)) out.set(id, data.pending.generated_on);
  }
  return out;
}

/** A timeline entry's dated pending note, or null when it reads as enforced.
 *  Linked to a pending diff: dated by that diff. Otherwise dated after this
 *  build: dated by the build. An entry with only an 施行日 comment past its
 *  date gets no claim either way — its date line quotes e-Gov instead. */
export function entryPendingNote(
  e: TimelineEntry,
  generatedOn: Map<string, string>
): string | null {
  const gen = e.diff_id ? generatedOn.get(e.diff_id) : undefined;
  if (gen) return asOfLabel(gen);
  if (e.enforcement_date > BUILD_DATE_JST) return asOfLabel(BUILD_DATE_JST);
  return null;
}

/** Whether an entry may stand for "the latest enforced amendment". */
export function isEnforcedEntry(
  e: TimelineEntry,
  generatedOn: Map<string, string>
): boolean {
  return (
    entryPendingNote(e, generatedOn) === null && !e.enforcement_comment
  );
}
