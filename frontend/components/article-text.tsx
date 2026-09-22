import { CurrentText, FormerText } from "@/lib/types";
import { jpDate } from "@/lib/format";
// FormerText keeps the plain Paragraph shape: it comes from the shipped diff,
// which has no margin marks.

export function ArticleText({
  current,
  asof,
  displayNum,
}: {
  current: CurrentText;
  asof: string;
  displayNum: string;
}) {
  return (
    <section className="border border-[var(--border)] rounded-lg p-4">
      {/* Never "現在の条文" alone: this is a static page and the law moves. */}
      <h2 className="text-[14px] font-bold mb-3">現在の条文（{jpDate(asof)}時点）</h2>
      {/* Two tombstone statuses need two different sentences: a number folded
          into a range node (merged_deleted) is 欠番, but a standalone repeal
          (deleted) was folded into nothing, so the 欠番 wording would be false
          for it. See TOMBSTONE_STATUSES in lib/types.ts. */}
      {current.status === "merged_deleted" && (
        <p className="mb-3 text-[13px] opacity-70">
          {displayNum}は「{current.source_label}」として欠番になっています。
        </p>
      )}
      {current.status === "deleted" && (
        <p className="mb-3 text-[13px] opacity-70">
          {displayNum}は削除されています。現在の本文は「削除」の一語のみで、条文の内容はありません。
        </p>
      )}
      {current.paragraphs.map((p) => (
        <p key={p.num} className="whitespace-pre-wrap leading-[26px]">
          {/* The margin number the printed law carries. Without it 民法772条
              reads as four unnumbered blocks and 第2項 cannot be located. */}
          {p.mark && <span className="mr-2 opacity-70">{p.mark}</span>}
          {p.text}
        </p>
      ))}
    </section>
  );
}

export function FormerArticleText({ former }: { former: FormerText }) {
  return (
    <section className="border border-[var(--border)] bg-[var(--muted)] rounded-lg p-4">
      {/* "削除される前の条文" is wrong for 民法753条, whose previous text was
          already the word 削除 -- what this amendment removed was the empty
          slot itself. The spec's wording says only what we know: the text as it
          stood immediately before this amendment. */}
      <h2 className="text-[14px] font-bold mb-1">
        今回の改正直前の条文（{jpDate(former.as_of)}時点）
      </h2>
      <p className="mb-3 text-[13px] opacity-70">現行法ではありません。</p>
      {former.paragraphs.map((p) => (
        <p key={p.num} className="whitespace-pre-wrap leading-[26px]">
          {p.text}
        </p>
      ))}
    </section>
  );
}
