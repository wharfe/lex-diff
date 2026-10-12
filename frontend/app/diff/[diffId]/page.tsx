import type { Metadata } from "next";
import {
  getDiffIds,
  getDiffData,
  mainChangeCounts,
  getArticleLawIds,
  getArticleData,
} from "@/lib/data";
import { RevisionHeader } from "@/components/revision-header";
import { PrSummaryCard } from "@/components/pr-summary";
import { DiffViewer } from "@/components/diff-viewer";
import { BreadcrumbJsonLd } from "@/components/breadcrumb-jsonld";
import {
  asOfLabel,
  enforcementLabel,
  isPendingDiff,
  pendingName,
} from "@/lib/pending";

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
  // 本則 only — see mainChangeCounts. Folding 附則 in claimed "2条が変更され
  // ました" for an amendment that changed no article of the main text at all.
  const { total: mainCount, supplTotal: supplCount } = mainChangeCounts(
    data.diffs
  );
  if (isPendingDiff(data)) {
    // No year and no past tense: the date may be a 政令 deadline, and the
    // page stays as built after it passes. Every claim is dated instead.
    const name = pendingName(data);
    const asOf = asOfLabel(data.pending.generated_on);
    const dates = data.pending.revisions
      .map((r) => enforcementLabel(r, data.date_after))
      .join("／");
    const change =
      mainCount > 0
        ? `施行されると本則${mainCount}条が変わります。`
        : `施行されると附則${supplCount}件が変わります（本則は変わりません）。`;
    const pendingTitle = `${data.law_title}【${asOf}】${name}による改正`;
    const description = `${data.law_title}の改正（${name}、${asOf}）による新旧条文の差分。施行日: ${dates}。${change}`;
    return {
      title: pendingTitle,
      description,
      alternates: { canonical: `/diff/${encodeURIComponent(diffId)}` },
      openGraph: { title: `${pendingTitle} | lexdiff`, description },
    };
  }
  const title = data.pr_summary?.title || data.revision_after.amendment_law_title;
  const year = data.date_after.slice(0, 4);
  const changeSummary =
    mainCount > 0
      ? `${title}で本則${mainCount}条が変更されました。`
      : `${title}。本則の条文は変わらず、附則（施行期日・経過措置・特例など）${supplCount}件のみの改正です。`;
  return {
    title: `${data.law_title}【${year}年改正】${title}`,
    description: `${data.law_title}の${year}年改正による新旧条文の差分。${changeSummary}改正前後の条文を並べて確認できます。`,
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
  // 労働基準法 has 0 本則 changes and ships no articles/ file; calling
  // getArticleData unconditionally would throw and break its two
  // 附則-only diff builds.
  const articleSlugs: Record<string, string> = getArticleLawIds().includes(
    data.law_id
  )
    ? Object.fromEntries(
        getArticleData(data.law_id).articles.map((a) => [a.article_num, a.slug])
      )
    : {};

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
            name: isPendingDiff(data)
              ? `${pendingName(data)}による改正（${asOfLabel(data.pending.generated_on)}）`
              : data.pr_summary?.title || data.date_after,
            url: `https://lexdiff.com/diff/${encodeURIComponent(diffId)}`,
          },
        ]}
      />
      <RevisionHeader data={data} />
      {data.pr_summary && <PrSummaryCard summary={data.pr_summary} />}
      <DiffViewer
        pending={isPendingDiff(data)}
        diffs={data.diffs}
        lawId={data.law_id}
        articleSlugs={articleSlugs}
      />
    </div>
  );
}
