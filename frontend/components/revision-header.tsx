import { LawDiffData } from "@/lib/types";
import { DiffStats } from "./diff-stats";
import { Icon } from "./icon";

function getEgovUrl(lawId: string): string {
  return `https://laws.e-gov.go.jp/law/${lawId}`;
}

export function RevisionHeader({ data }: { data: LawDiffData }) {
  const { proposer } = data;

  return (
    <div className="border border-[var(--border)] rounded-lg p-4 md:p-6 bg-[var(--muted)]">
      <h1 className="text-[20px] font-bold mb-1">{data.law_title}</h1>
      <p className="text-[14px] opacity-70 mb-4">
        {data.revision_after.amendment_law_title}
      </p>

      {/* Proposer info — git commit author style */}
      {proposer?.minister && (
        <div className="flex items-center gap-2 text-[14px] mb-4 flex-wrap">
          <span className="font-medium">{proposer.minister.name}</span>
          {proposer.minister.position && (
            <span className="opacity-50 text-[13px]">
              {proposer.minister.position.split("・")[0]}
            </span>
          )}
          {proposer.submission_type && (
            <span className="rounded-full bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] px-2 py-0.5 text-[11px] font-medium">
              {proposer.submission_type}
            </span>
          )}
          {proposer.committee && (
            <span className="opacity-40 text-[13px]">
              {proposer.committee}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 text-[13px] mb-4 flex-wrap">
        <span className="inline-flex items-center gap-1 rounded-full bg-[var(--diff-del-bg)] px-3 py-1 text-[var(--diff-del-text)] font-mono">
          {data.date_before}
        </span>
        <span className="opacity-30">&rarr;</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-[var(--diff-add-bg)] px-3 py-1 text-[var(--diff-add-text)] font-mono">
          {data.date_after}
        </span>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-2">
        <DiffStats data={data} />
        <a
          href={getEgovUrl(data.law_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[13px] text-[var(--diff-hunk-text)] hover:underline"
        >
          e-Gov法令検索で原文を見る{" "}
          <Icon name="open_in_new" size={12} />
        </a>
      </div>
    </div>
  );
}
