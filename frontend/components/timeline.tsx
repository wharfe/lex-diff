import Link from "next/link";
import { TimelineEntry } from "@/lib/types";

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
  index,
}: {
  entry: TimelineEntry;
  index: number;
}) {
  const hasDiff = entry.diff_id !== null;
  const hash = shortHash(entry.law_revision_id);

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
        <span className="opacity-70">{entry.enforcement_date}</span>
        {hasDiff && (
          <span className="text-[var(--diff-add-text)] text-[12px]">
            差分あり
          </span>
        )}
      </div>

      {/* Line 2: commit message */}
      <div className="ml-8 mt-1.5">
        <span className="text-[14px] leading-[22px]">
          {entry.amendment_law_title}
        </span>
      </div>

      {/* Line 3: promulgation date if different */}
      {entry.promulgate_date &&
        entry.promulgate_date !== entry.enforcement_date && (
          <div className="ml-8 mt-1 text-[12px] opacity-40">
            公布: {entry.promulgate_date}
          </div>
        )}
    </>
  );
}

export function Timeline({
  entries,
}: {
  entries: TimelineEntry[];
  lawId: string;
}) {
  return (
    <div className="text-[14px]">
      {entries.map((entry, i) => {
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
              <EntryContent entry={entry} index={i} />
            </Link>
          );
        }

        return (
          <div key={entry.law_revision_id} className={className}>
            <EntryContent entry={entry} index={i} />
          </div>
        );
      })}
    </div>
  );
}
