import { getTimelineIds, getTimelineData } from "@/lib/data";
import { Timeline } from "@/components/timeline";
import { Icon } from "@/components/icon";

export function generateStaticParams() {
  return getTimelineIds().map((lawId) => ({ lawId }));
}

export default async function LawPage({
  params,
}: {
  params: Promise<{ lawId: string }>;
}) {
  const { lawId } = await params;
  const data = getTimelineData(lawId);

  return (
    <div className="flex flex-col gap-6">
      {/* Repository-style header */}
      <div>
        <div className="flex items-center gap-2 text-[15px] mb-2">
          <a href="/" className="opacity-50 hover:underline">
            lex-diff
          </a>
          <span className="opacity-30">/</span>
          <span className="font-bold">{data.law_title}</span>
        </div>
        <p className="text-[13px] opacity-40 font-mono mb-4">{data.law_num}</p>

        <div className="flex items-center gap-4 border border-[var(--border)] rounded-lg px-4 py-3 bg-[var(--muted)] text-[14px] flex-wrap">
          <div className="flex items-center gap-1.5">
            <Icon name="history" size={16} className="opacity-40" />
            <span className="font-mono font-bold">
              {data.revision_count}
            </span>
            <span className="opacity-50">commits</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Icon name="calendar_month" size={16} className="opacity-40" />
            <span className="opacity-50">since</span>
            <span className="font-mono">{data.promulgation_date}</span>
          </div>
          <div className="ml-auto">
            <a
              href={`https://laws.e-gov.go.jp/law/${data.law_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[13px] text-[var(--diff-hunk-text)] hover:underline"
            >
              原文 <Icon name="open_in_new" size={12} className="inline" />
            </a>
          </div>
        </div>
      </div>

      {/* Git log */}
      <div className="border border-[var(--border)] rounded-lg overflow-hidden">
        <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] text-[14px] font-medium">
          改正履歴
        </div>
        <Timeline entries={data.timeline} lawId={data.law_id} />
      </div>
    </div>
  );
}
