import Link from "next/link";
import { DiffGap, DiffLine } from "@/components/diff-line";
import { articleDiffRows } from "@/lib/diff-lines";
import { jpDate } from "@/lib/format";
import { ArticleDiff, LatestChange } from "@/lib/types";

/** "This article's text took its present form on D", with that day's lines for
 *  this article (#44, docs/article-latest-diff/spec.md).
 *
 *  Every claim is dated: asof is the day the current text was fetched, and a
 *  static page is not rebuilt when the law moves on. It says 本文 because a
 *  caption change is invisible to both the diff and the gate. It names no
 *  amending law: several can take effect on one day, and one diff cannot tell
 *  their changes apart -- hence 「この日の改正」 on the link. */
export function ArticleLatestChange({
  change,
  entry,
  asof,
  articleNum,
}: {
  change: LatestChange;
  entry: ArticleDiff;
  asof: string;
  articleNum: string;
}) {
  return (
    <section data-latest-change="">
      <h2 className="text-[14px] font-bold mb-2">この条文の最後の変更</h2>
      <p className="leading-[26px] mb-3">
        {jpDate(asof)}時点のこの条文の本文は、{jpDate(change.enforcement_date)}
        施行の改正で今の形になりました。
      </p>
      <div className="border border-[var(--border)] rounded-lg overflow-hidden py-1">
        {articleDiffRows(entry.diff, entry.lines_after.length).map((row, i) =>
          row.kind === "gap" ? <DiffGap key={i} /> : <DiffLine key={i} line={row.line} />,
        )}
      </div>
      <Link
        href={`/diff/${change.diff_id}#${articleNum}`}
        className="mt-2 inline-block text-[14px] text-[var(--diff-hunk-text)]"
      >
        この日の改正の全体を見る →
      </Link>
    </section>
  );
}
