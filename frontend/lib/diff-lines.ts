/** Helpers for the unified-diff lines diff.py ships (one array per article). */

/** A "+" or "-" line of the diff body; the "+++"/"---" file headers are not. */
export function isChangedLine(line: string): boolean {
  return (line.startsWith("+") && !line.startsWith("+++")) ||
    (line.startsWith("-") && !line.startsWith("---"));
}

const HUNK = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

export type ArticleDiffRow = { kind: "line"; line: string } | { kind: "gap" };

/** The rows the article page draws: diff lines, with a gap marker wherever
 *  lines of the article were left out -- before the first hunk when it does
 *  not start at line 1, between hunks, and after the last hunk when it ends
 *  before the article does. A hunk header is never drawn: the /diff page's
 *  "@@ -2,7 +2,7 @@" means nothing to someone who searched for an article.
 *
 *  `totalAfter` is the article's line count after the amendment
 *  (lines_after.length), the side whose numbers the "+" half of a header uses.
 *  A header that does not parse throws: guessing where text was omitted would
 *  draw an excerpt as if it were the whole article. */
export function articleDiffRows(lines: string[], totalAfter: number): ArticleDiffRow[] {
  const rows: ArticleDiffRow[] = [];
  let lastEnd = 0; // last line number on the "+" side covered so far
  let sawHunk = false;
  for (const line of lines) {
    if (line.startsWith("+++") || line.startsWith("---")) continue;
    if (line.startsWith("@@")) {
      const m = HUNK.exec(line);
      if (!m) throw new Error(`unparseable hunk header: ${line}`);
      const oldStart = Number(m[1]);
      const newStart = Number(m[3]);
      const newCount = m[4] === undefined ? 1 : Number(m[4]);
      // "-0,0" / "+0,0" is an empty side: an added or deleted article.
      const startsAtTop = (oldStart <= 1) && (newStart <= 1);
      if (sawHunk ? newStart > lastEnd + 1 : !startsAtTop) rows.push({ kind: "gap" });
      lastEnd = newCount === 0 ? newStart : newStart + newCount - 1;
      sawHunk = true;
      continue;
    }
    rows.push({ kind: "line", line });
  }
  if (sawHunk && lastEnd < totalAfter) rows.push({ kind: "gap" });
  return rows;
}
