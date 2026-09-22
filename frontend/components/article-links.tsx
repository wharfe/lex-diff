import Link from "next/link";
import { RelatedArticle } from "@/lib/types";

export function ArticleLinks({
  lawId,
  related,
}: {
  lawId: string;
  related: RelatedArticle[];
}) {
  if (related.length === 0) return null;
  return (
    <section>
      <h2 className="text-[14px] font-bold mb-3">関連する条文</h2>
      <ul className="flex flex-col gap-2">
        {related.map((r, i) => (
          <li key={`${r.ref}-${i}`} className="text-[13px]">
            {r.has_page && r.slug ? (
              <Link
                href={`/law/${lawId}/article/${r.slug}`}
                className="text-[var(--diff-hunk-text)]"
              >
                {r.ref}
              </Link>
            ) : (
              <span>{r.ref}</span>
            )}
            {/* context is often "": Python blanks it unless the target has a
                page that passed the version gate, so an unverified sentence
                about the target is never printed. Rendering the span anyway
                would leave a dangling margin with nothing after it. */}
            {r.context && <span className="ml-2 opacity-70">{r.context}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
