import type { Metadata } from "next";
import { getDiffIds, getDiffData } from "@/lib/data";
import { RevisionHeader } from "@/components/revision-header";
import { PrSummaryCard } from "@/components/pr-summary";
import { DiffViewer } from "@/components/diff-viewer";
import { BreadcrumbJsonLd } from "@/components/breadcrumb-jsonld";

export function generateStaticParams() {
  return getDiffIds().map((diffId) => ({ diffId }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ diffId: string }>;
}): Promise<Metadata> {
  const { diffId } = await params;
  const data = getDiffData(decodeURIComponent(diffId));
  const title = data.pr_summary?.title || data.revision_after.amendment_law_title;
  const year = data.date_after.slice(0, 4);
  const changedCount = data.stats.added + data.stats.modified + data.stats.deleted;
  return {
    title: `${data.law_title}【${year}年改正】${title}`,
    description: `${data.law_title}の${year}年改正による新旧条文の差分。${title}で${changedCount}条が変更されました。改正前後の条文を並べて確認できます。`,
    alternates: { canonical: `/diff/${encodeURIComponent(diffId)}` },
    openGraph: {
      title: `${data.law_title}【${year}年改正】${title} | lexdiff`,
      description: data.pr_summary?.summary || title,
    },
  };
}

export default async function DiffPage({
  params,
}: {
  params: Promise<{ diffId: string }>;
}) {
  const { diffId } = await params;
  const data = getDiffData(decodeURIComponent(diffId));

  return (
    <div className="flex flex-col gap-6">
      <BreadcrumbJsonLd
        items={[
          { name: "lexdiff", url: "https://lexdiff.com" },
          {
            name: data.law_title,
            url: `https://lexdiff.com/law/${data.law_id}`,
          },
          {
            name: data.pr_summary?.title || data.date_after,
            url: `https://lexdiff.com/diff/${encodeURIComponent(diffId)}`,
          },
        ]}
      />
      <RevisionHeader data={data} />
      {data.pr_summary && <PrSummaryCard summary={data.pr_summary} />}
      <DiffViewer diffs={data.diffs} />
    </div>
  );
}
