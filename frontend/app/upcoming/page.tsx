import type { Metadata } from "next";
import Link from "next/link";
import { getDiffIds, getDiffData, mainChangeCounts } from "@/lib/data";
import {
  asOfLabel,
  BUILD_DATE_JST,
  enforcementLinesFor,
  groupUpcoming,
  pendingName,
  pendingStatsLabel,
  PENDING_SECTION_INTRO,
  type PendingDiff,
  UPCOMING_DESCRIPTION,
  UPCOMING_EMPTY,
  UPCOMING_SCOPE,
  UPCOMING_TITLE,
  upcomingBeforeNote,
  upcomingPending,
} from "@/lib/pending";

// docs/upcoming-page/spec.md. Every string is from lib/pending.ts, and
// scripts/check_upcoming_page.py checks the built page against the data.

export const metadata: Metadata = {
  title: UPCOMING_TITLE,
  description: UPCOMING_DESCRIPTION,
  alternates: { canonical: "/upcoming" },
  // Restated in full: a page-level openGraph replaces the root one.
  openGraph: {
    title: `${UPCOMING_TITLE} | lexdiff`,
    description: UPCOMING_DESCRIPTION,
    url: "https://lexdiff.com/upcoming",
    siteName: "lexdiff",
    locale: "ja_JP",
    type: "website",
  },
};

type Row = { id: string; data: PendingDiff };

function UpcomingRow({ id, data }: Row) {
  const before = upcomingBeforeNote(data);
  return (
    <Link
      href={`/diff/${encodeURIComponent(id)}`}
      data-pending-id={id}
      className="block px-4 py-3 border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--muted)] transition-colors"
    >
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-bold text-[14px]">{data.law_title}</span>
        <span className="text-[13px] opacity-70">{pendingName(data)}</span>
        <span className="rounded-full bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] px-2 py-0.5 text-[11px]">
          {asOfLabel(data.pending.generated_on)}
        </span>
      </div>
      <p className="text-[12px] opacity-60 mt-1 break-words">{enforcementLinesFor(data)}</p>
      <p className="text-[12px] opacity-60 mt-0.5">
        {pendingStatsLabel(mainChangeCounts(data.diffs).total)}
        {before}
      </p>
    </Link>
  );
}

function UpcomingSection({ k, heading, rows }: { k: string; heading: string; rows: Row[] }) {
  return (
    <section data-upcoming-section={k}>
      <h2 className="text-[17px] font-bold mb-3">{heading}</h2>
      <div className="border border-[var(--border)] rounded-lg overflow-hidden">
        {rows.map((r) => (
          <UpcomingRow key={r.id} {...r} />
        ))}
      </div>
    </section>
  );
}

export default function UpcomingPage() {
  const rows = upcomingPending(getDiffIds().map((id) => ({ id, data: getDiffData(id) })));

  return (
    <div className="flex flex-col gap-8" data-build-date={BUILD_DATE_JST}>
      <header>
        <h1 className="text-2xl font-bold">{UPCOMING_TITLE}</h1>
        <p className="mt-2 text-[14px] opacity-70">{PENDING_SECTION_INTRO}</p>
        <p className="mt-1 text-[13px] opacity-50">{UPCOMING_SCOPE}</p>
      </header>

      {rows.length === 0 && <p className="text-[14px] opacity-70">{UPCOMING_EMPTY}</p>}

      {groupUpcoming(rows).map((s) => (
        <UpcomingSection key={s.key} k={s.key} heading={s.heading} rows={s.rows} />
      ))}
    </div>
  );
}
