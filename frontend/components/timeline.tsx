import Link from "next/link";
import { TimelineEntry } from "@/lib/types";
import { entryPendingNote } from "@/lib/pending";

function shortHash(revisionId: string): string {
  let hash = 0;
  for (let i = 0; i < revisionId.length; i++) {
    const char = revisionId.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return Math.abs(hash).toString(16).slice(0, 7).padStart(7, "0");
}

function EntryContent({
  entry,
  pendingGeneratedOn,
}: {
  entry: TimelineEntry;
  pendingGeneratedOn: Map<string, string>;
}) {
  const hasDiff = entry.diff_id !== null;
  const hash = shortHash(entry.law_revision_id);
  const pendingNote = entryPendingNote(entry, pendingGeneratedOn);

  return (
    <>
      {/* Line 1: graph + hash + date */}
      <div className="flex items-center gap-3 font-mono text-[13px]">
        <span className="text-[var(--diff-hunk-text)] select-none">
          *
        </span>
        <span
          className={
            hasDiff ? "text-[var(--diff-hunk-text)]" : "opacity-50"
          }
        >
          {hash}
        </span>
        <span className="opacity-70">
          {entry.enforcement_date}
          {/* Not fixed yet: the date above is e-Gov's scheduled one. */}
          {entry.enforcement_comment && "（予定日）"}
        </span>
        {pendingNote && (
          <span className="rounded-full bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] px-2 py-0.5 text-[11px] font-sans">
            {pendingNote}
          </span>
        )}
        {hasDiff && (
          <span className="text-[var(--diff-add-text)] text-[12px]">
            差分あり
          </span>
        )}
      </div>
      {entry.enforcement_comment && (
        <div className="ml-8 mt-1 text-[12px] opacity-60">
          施行日: {entry.enforcement_comment}（e-Gov 上の予定日: {entry.enforcement_date}）
        </div>
      )}

      {/* Line 2: commit message */}
      <div className="ml-8 mt-1.5">
        <span className="text-[14px] leading-[22px]">
          {entry.amendment_law_title}
        </span>
      </div>

      {/* Line 3: author + metadata */}
      <div className="ml-8 mt-1 flex items-center gap-3 flex-wrap text-[12px] opacity-50">
        {entry.proposer?.minister?.name && (
          <span>
            {entry.proposer.minister.name}
            {entry.proposer.minister.position && (
              <span className="opacity-60">
                （{entry.proposer.minister.position.split("・")[0]}）
              </span>
            )}
          </span>
        )}
        {entry.proposer?.submission_type && (
          <span className="font-mono">{entry.proposer.submission_type}</span>
        )}
        {entry.proposer?.committee && (
          <span>{entry.proposer.committee}</span>
        )}
        {entry.promulgate_date &&
          entry.promulgate_date !== entry.enforcement_date && (
            <span>公布: {entry.promulgate_date}</span>
          )}
      </div>
    </>
  );
}

export function Timeline({
  entries,
  pendingGeneratedOn,
}: {
  entries: TimelineEntry[];
  lawId: string;
  /** pending.py diff ids → build date; see getPendingGeneratedOn. */
  pendingGeneratedOn: Map<string, string>;
}) {
  return (
    <div className="text-[14px]">
      {entries.map((entry) => {
        const hasDiff = entry.diff_id !== null;
        const className = `block border-b border-[var(--border)] px-4 py-4 ${
          hasDiff ? "hover:bg-[var(--muted)] cursor-pointer" : "opacity-60"
        }`;

        if (hasDiff) {
          return (
            <Link
              key={entry.law_revision_id}
              href={`/diff/${encodeURIComponent(entry.diff_id!)}`}
              className={className}
            >
              <EntryContent entry={entry} pendingGeneratedOn={pendingGeneratedOn} />
            </Link>
          );
        }

        return (
          <div key={entry.law_revision_id} className={className}>
            <EntryContent entry={entry} pendingGeneratedOn={pendingGeneratedOn} />
          </div>
        );
      })}
    </div>
  );
}
