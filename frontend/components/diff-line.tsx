import { isChangedLine } from "@/lib/diff-lines";

/** One unified-diff line. Deliberately not a client component: the article
 *  page renders it on the server, and importing it from the "use client"
 *  diff-viewer shipped that module's JS and every line twice (HTML + RSC
 *  payload) on 401 static pages. */
export function DiffLine({ line }: { line: string }) {
  const changed = isChangedLine(line);
  const isAdd = changed && line.startsWith("+");
  const isDel = changed && line.startsWith("-");
  const isHunk = line.startsWith("@@");
  const isMeta = line.startsWith("---") || line.startsWith("+++");

  if (isMeta) return null;

  let className =
    "px-4 py-1 font-mono text-[13px] leading-[22px] whitespace-pre-wrap ";
  let prefix = " ";

  if (isAdd) {
    className += "bg-[var(--diff-add-bg)] text-[var(--diff-add-text)]";
    prefix = "+";
  } else if (isDel) {
    className += "bg-[var(--diff-del-bg)] text-[var(--diff-del-text)]";
    prefix = "-";
  } else if (isHunk) {
    className +=
      "bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] py-1.5";
    prefix = "";
  } else {
    className += "text-[var(--foreground)]";
  }

  const content = isAdd || isDel ? line.slice(1) : line;

  return (
    <div className={className}>
      <span className="inline-block w-5 select-none opacity-50 text-right mr-2">
        {prefix}
      </span>
      {content}
    </div>
  );
}

/** Where the article page left lines out. */
export function DiffGap() {
  return (
    <div className="px-4 py-1 text-[12px] opacity-40 select-none" aria-hidden="true">
      ⋯
    </div>
  );
}
