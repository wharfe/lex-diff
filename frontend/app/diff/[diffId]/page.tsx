import { getDiffIds, getDiffData } from "@/lib/data";
import { RevisionHeader } from "@/components/revision-header";
import { PrSummaryCard } from "@/components/pr-summary";
import { DiffViewer } from "@/components/diff-viewer";

export function generateStaticParams() {
  return getDiffIds().map((diffId) => ({ diffId }));
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
      <RevisionHeader data={data} />
      {data.pr_summary && <PrSummaryCard summary={data.pr_summary} />}
      <DiffViewer diffs={data.diffs} />
    </div>
  );
}
