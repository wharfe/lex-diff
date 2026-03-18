import type { Metadata } from "next";
import { getTimelineIds, getTimelineData } from "@/lib/data";
import { Timeline } from "@/components/timeline";
import { Icon } from "@/components/icon";
import { getThemesForLaw } from "@/lib/life-themes";
import { BreadcrumbJsonLd } from "@/components/breadcrumb-jsonld";

export function generateStaticParams() {
  return getTimelineIds().map((lawId) => ({ lawId }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lawId: string }>;
}): Promise<Metadata> {
  const { lawId } = await params;
  const data = getTimelineData(lawId);
  const desc = data.summary?.description || `${data.law_title}の改正履歴`;
  return {
    title: `${data.law_title} 改正履歴`,
    description: desc,
    openGraph: {
      title: `${data.law_title} 改正履歴 | lexdiff`,
      description: desc,
    },
  };
}

export default async function LawPage({
  params,
}: {
  params: Promise<{ lawId: string }>;
}) {
  const { lawId } = await params;
  const data = getTimelineData(lawId);
  const themes = getThemesForLaw(lawId);

  return (
    <div className="flex flex-col gap-6">
      <BreadcrumbJsonLd
        items={[
          { name: "lexdiff", url: "https://lexdiff.com" },
          {
            name: data.law_title,
            url: `https://lexdiff.com/law/${lawId}`,
          },
        ]}
      />
      {/* Repository-style header */}
      <div>
        <div className="flex items-center gap-2 text-[15px] mb-2">
          <a href="/" className="opacity-50 hover:underline">
            lex-diff
          </a>
          <span className="opacity-30">/</span>
          <span className="font-bold">{data.law_title}</span>
        </div>
        <p className="text-[13px] opacity-40 font-mono mb-4">
          {data.law_num}
        </p>

        <div className="flex items-center gap-4 border border-[var(--border)] rounded-lg px-4 py-3 bg-[var(--muted)] text-[14px] flex-wrap">
          <div className="flex items-center gap-1.5">
            <Icon name="history" size={16} className="opacity-40" />
            <span className="font-mono font-bold">
              {data.revision_count}
            </span>
            <span className="opacity-50">commits</span>
          </div>
          {data.contributors && data.contributors.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="font-mono font-bold">
                {data.contributors.length}
              </span>
              <span className="opacity-50">contributors</span>
            </div>
          )}
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
              原文{" "}
              <Icon name="open_in_new" size={12} className="inline" />
            </a>
          </div>
        </div>
      </div>

      {/* README-style description */}
      {data.summary && (
        <div className="border border-[var(--border)] rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] flex items-center gap-2">
            <Icon name="description" size={16} className="opacity-40" />
            <span className="text-[14px] font-medium">この法律について</span>
            <span className="text-[11px] opacity-40 ml-auto">AI要約</span>
          </div>
          <div className="px-4 py-4 space-y-3">
            <p className="text-[15px] leading-[26px]">
              {data.summary.description}
            </p>
            {data.summary.scope && (
              <p className="text-[14px] leading-[24px] opacity-60">
                <span className="font-medium opacity-100">適用範囲：</span>
                {data.summary.scope}
              </p>
            )}
            {data.summary.keywords && data.summary.keywords.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {data.summary.keywords.map((kw) => (
                  <span
                    key={kw}
                    className="rounded-full bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] px-2.5 py-0.5 text-[12px]"
                  >
                    {kw}
                  </span>
                ))}
                {data.category && (
                  <span className="rounded-full bg-[var(--muted)] border border-[var(--border)] px-2.5 py-0.5 text-[12px] opacity-50">
                    {data.category}
                  </span>
                )}
              </div>
            )}
            {themes.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {themes.map((t) => (
                  <span
                    key={t.id}
                    className="text-[12px] opacity-50"
                  >
                    {t.label}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Git log — main content */}
        <div className="flex-1 min-w-0">
          <div className="border border-[var(--border)] rounded-lg overflow-hidden">
            <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] text-[14px] font-medium">
              改正履歴
            </div>
            <Timeline entries={data.timeline} lawId={data.law_id} />
          </div>
        </div>

        {/* Sidebar — Contributors */}
        {data.contributors && data.contributors.length > 0 && (
          <div className="lg:w-[260px] shrink-0">
            <div className="border border-[var(--border)] rounded-lg overflow-hidden">
              <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] text-[14px] font-medium">
                Contributors
              </div>
              <div className="px-4 py-3 space-y-3">
                {data.contributors.map((c) => (
                  <div key={c.name} className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-[var(--diff-hunk-bg)] flex items-center justify-center text-[11px] font-bold text-[var(--diff-hunk-text)] shrink-0">
                      {c.name.charAt(0)}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium truncate">
                        {c.name}
                      </div>
                      <div className="text-[11px] opacity-40 truncate">
                        {c.position.split("・")[0]}
                      </div>
                    </div>
                    <span className="ml-auto text-[12px] font-mono opacity-40 shrink-0">
                      {c.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
