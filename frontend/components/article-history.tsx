import Link from "next/link";
import { ArticleChange } from "@/lib/types";
import { jpDate } from "@/lib/format";

export function ArticleHistory({
  changes,
  anchor,
}: {
  changes: ArticleChange[];
  /** The article_num, which is the id the /diff card carries. */
  anchor: string;
}) {
  return (
    <section>
      <h2 className="text-[14px] font-bold mb-3">この条文の改正履歴</h2>
      <ol className="flex flex-col gap-4">
        {changes.map((c) => (
          <li
            key={c.diff_id + c.enforcement_date}
            className="border border-[var(--border)] rounded-lg p-4"
          >
            <p className="text-[13px] opacity-70">
              {jpDate(c.enforcement_date)}施行・{c.amendment_law_title}
            </p>
            <p className="mt-2 whitespace-pre-wrap leading-[26px]">{c.change_description}</p>
            {c.plain_summary && (
              // A deleted article has no text just after the amendment -- the
              // note describes what stood there just before. 民法754条's
              // paragraphs_after is empty (measured), so "改正直後" would label
              // a description of the repealed rule as a description of 削除.
              <p className="mt-2 text-[13px] opacity-70">
                {jpDate(c.enforcement_date)}
                {c.type === "deleted" ? "改正直前" : "改正直後"}の条文についての説明:{" "}
                {c.plain_summary}
              </p>
            )}
            {c.cross_references.length > 0 && (
              // Text, not links: a reference written about an older version of
              // this article may point at a provision that has since moved.
              <p className="mt-2 text-[13px] opacity-70">
                当時の関連条文: {c.cross_references.map((r) => r.ref).join("、")}
              </p>
            )}
            <Link
              href={`/diff/${c.diff_id}#${anchor}`}
              className="mt-2 inline-block text-[13px] text-[var(--diff-hunk-text)]"
            >
              この改正の全体を見る →
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
