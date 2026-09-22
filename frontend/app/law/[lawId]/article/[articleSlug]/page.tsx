import type { Metadata } from "next";
import Link from "next/link";
import { getArticleParams, getArticleData, findArticle } from "@/lib/data";
import { isTombstone } from "@/lib/types";
import { ArticleText, FormerArticleText } from "@/components/article-text";
import { ArticleHistory } from "@/components/article-history";
import { ArticleLinks } from "@/components/article-links";
import { BreadcrumbJsonLd } from "@/components/breadcrumb-jsonld";
import { jpDate } from "@/lib/format";

export function generateStaticParams() {
  const params = getArticleParams();
  // The build is the only feedback that reaches anyone here, so make it fail.
  const seen = new Set(params.map((p) => `${p.lawId}/${p.articleSlug}`));
  if (params.length === 0 || seen.size !== params.length) {
    throw new Error(`article params are empty or contain duplicates (${params.length})`);
  }
  return params;
}

/** "民法第306条（一般の先取特権）", or without the parenthesis when the current
 *  text carries no caption -- 民法754条 has none, and an empty （） is worse
 *  than no caption at all. */
function head(lawTitle: string, displayNum: string, caption: string): string {
  return caption ? `${lawTitle}${displayNum}（${caption}）` : `${lawTitle}${displayNum}`;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lawId: string; articleSlug: string }>;
}): Promise<Metadata> {
  const { lawId, articleSlug } = await params;
  const data = getArticleData(lawId);
  const article = findArticle(lawId, articleSlug)!;
  const title = head(data.law_title, article.display_num, article.caption);
  const years = [...new Set(article.changes.map((c) => c.year))].join("・");
  // Only what every page actually carries: the dated text and the amendment
  // years we hold. "改正前後の条文" is true of deleted articles alone, and the
  // related-article links are absent on a page whose text has moved on.
  return {
    title: `${title}の条文と改正（${years}年改正）`,
    description: `${title}の${jpDate(data.source.asof)}時点の条文と、${years}年の改正内容。`,
    alternates: { canonical: `/law/${lawId}/article/${articleSlug}` },
  };
}

export default async function ArticlePageRoute({
  params,
}: {
  params: Promise<{ lawId: string; articleSlug: string }>;
}) {
  const { lawId, articleSlug } = await params;
  const data = getArticleData(lawId);
  const article = findArticle(lawId, articleSlug)!;
  const title = head(data.law_title, article.display_num, article.caption);

  return (
    <div className="flex flex-col gap-6">
      <BreadcrumbJsonLd
        items={[
          { name: "lexdiff", url: "https://lexdiff.com" },
          { name: data.law_title, url: `https://lexdiff.com/law/${lawId}` },
          {
            name: article.display_num,
            url: `https://lexdiff.com/law/${lawId}/article/${articleSlug}`,
          },
        ]}
      />
      <header>
        <h1 className="text-2xl font-bold">{title}</h1>
        {article.section_path.length > 0 && (
          <p className="mt-1 text-[13px] opacity-70">{article.section_path.join(" › ")}</p>
        )}
      </header>

      <ArticleText
        current={article.current}
        asof={data.source.asof}
        displayNum={article.display_num}
      />

      {/* spec §6: a tombstone page lists 現在の姿 → 改正直前の条文 → 改正履歴 →
          /diff リンク, with no summary slot. "現行本文に対応する解説は未収録
          です" asserts a current text whose explanation is merely missing --
          false for a repealed article, so the whole section is skipped here. */}
      {!isTombstone(article.current.status) && (
        <section>
          <h2 className="text-[14px] font-bold mb-2">この条文は何をする条文か</h2>
          {article.current_summary ? (
            <p className="leading-[26px]">{article.current_summary.text}</p>
          ) : (
            <p className="text-[13px] opacity-70">
              現行本文に対応する解説は未収録です。収録済み改正時点の説明は改正履歴で確認できます。
            </p>
          )}
        </section>
      )}

      {article.former && <FormerArticleText former={article.former} />}

      <ArticleHistory changes={article.changes} anchor={article.article_num} />
      <ArticleLinks lawId={lawId} related={article.related_articles} />

      <Link href={`/law/${lawId}`} className="text-[var(--diff-hunk-text)]">
        {data.law_title}の改正履歴をすべて見る →
      </Link>
    </div>
  );
}
