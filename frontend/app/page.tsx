import Link from "next/link";
import {
  getDiffIds,
  getDiffData,
  getTimelineIds,
  getTimelineData,
} from "@/lib/data";
import { LIFE_THEMES } from "@/lib/life-themes";
import { Icon } from "@/components/icon";

function DiffPreviewLine({ line }: { line: string }) {
  const isAdd = line.startsWith("+") && !line.startsWith("+++");
  const isDel = line.startsWith("-") && !line.startsWith("---");
  const isHunk = line.startsWith("@@");
  const isMeta = line.startsWith("---") || line.startsWith("+++");
  if (isMeta) return null;

  let className = "px-3 py-0.5 text-[12px] leading-[20px] font-mono truncate ";
  if (isAdd) className += "bg-[var(--diff-add-bg)] text-[var(--diff-add-text)]";
  else if (isDel)
    className += "bg-[var(--diff-del-bg)] text-[var(--diff-del-text)]";
  else if (isHunk)
    className += "bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)]";
  else className += "opacity-60";

  const prefix = isAdd ? "+" : isDel ? "-" : isHunk ? "" : " ";
  const content = isAdd || isDel ? line.slice(1) : line;

  return (
    <div className={className}>
      <span className="inline-block w-3 select-none opacity-50">{prefix}</span>
      {content}
    </div>
  );
}

export default function Home() {
  const timelineIds = getTimelineIds();
  const timelines = timelineIds.map((id) => ({
    id,
    data: getTimelineData(id),
  }));

  const diffIds = getDiffIds();
  const diffs = diffIds.map((id) => ({ id, data: getDiffData(id) }));

  // Pick the most interesting diff for the hero preview (most changes)
  const heroDiff = diffs.length > 0
    ? diffs.reduce((best, curr) =>
        (curr.data.stats.added + curr.data.stats.modified + curr.data.stats.deleted) >
        (best.data.stats.added + best.data.stats.modified + best.data.stats.deleted)
          ? curr : best
      )
    : null;

  // Get preview lines that show both additions and deletions
  const previewLines: string[] = [];
  if (heroDiff) {
    // Find a diff entry with both + and - lines
    const modified = heroDiff.data.diffs.find((d) => {
      if (d.type !== "modified") return false;
      const hasAdd = d.diff.some((l) => l.startsWith("+") && !l.startsWith("+++"));
      const hasDel = d.diff.some((l) => l.startsWith("-") && !l.startsWith("---"));
      return hasAdd && hasDel;
    }) || heroDiff.data.diffs.find((d) => d.type === "modified");
    if (modified) {
      let visibleCount = 0;
      for (const line of modified.diff) {
        // Skip meta lines (--- / +++) as they are hidden in render
        const isMeta = line.startsWith("---") || line.startsWith("+++");
        if (!isMeta) visibleCount++;
        if (visibleCount > 8) break;
        previewLines.push(line);
      }
    }
  }

  return (
    <div className="space-y-10">
      {/* Hero: concept at a glance */}
      <section className="relative">
        <div className="flex flex-col md:flex-row gap-6 items-start">
          <div className="flex-1 pt-2">
            <h1 className="text-[22px] md:text-[26px] font-bold leading-tight">
              法律が変わった。
              <br />
              何が変わったか、一目でわかる。
            </h1>
            <p className="mt-3 text-[15px] leading-[26px] opacity-60">
              法令の改正履歴を差分表示で可視化。
              いつ・どの条文が・どう変わったかを追えます。
            </p>
            {heroDiff && (
              <Link
                href={`/diff/${encodeURIComponent(heroDiff.id)}`}
                className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-lg bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] text-[14px] font-medium hover:opacity-80 transition-opacity"
              >
                <Icon name="difference" size={16} />
                最新のdiffを見る
              </Link>
            )}
          </div>

          {/* Live diff preview */}
          {previewLines.length > 0 && heroDiff && (
            <Link
              href={`/diff/${encodeURIComponent(heroDiff.id)}`}
              className="w-full md:w-[340px] lg:w-[400px] shrink-0 border border-[var(--border)] rounded-lg overflow-hidden hover:border-[var(--diff-hunk-text)] transition-colors"
            >
              <div className="bg-[var(--muted)] px-3 py-2 border-b border-[var(--border)] text-[12px] font-mono opacity-60 truncate">
                {heroDiff.data.diffs.find((d) => d.type === "modified")
                  ?.title_after || ""}
              </div>
              <div>
                {previewLines.map((line, i) => (
                  <DiffPreviewLine key={i} line={line} />
                ))}
              </div>
            </Link>
          )}
        </div>
      </section>

      {/* Recent diffs — card with inline preview */}
      {diffs.length > 0 && (
        <section>
          <h2 className="text-[17px] font-bold mb-4">最近の改正</h2>
          <div className="grid gap-4">
            {diffs.map(({ id, data }) => {
              const firstMod = data.diffs.find((d) => d.type === "modified");
              const preview = firstMod?.diff.filter(
                (l) => !l.startsWith("---") && !l.startsWith("+++")
              ).slice(0, 4) || [];
              return (
                <Link
                  key={id}
                  href={`/diff/${encodeURIComponent(id)}`}
                  className="block border border-[var(--border)] rounded-lg overflow-hidden hover:border-[var(--diff-hunk-text)]/50 transition-colors"
                >
                  <div className="px-4 py-3">
                    <div className="flex items-center gap-3 mb-1 flex-wrap">
                      <span className="text-[16px] font-bold">
                        {data.law_title}
                      </span>
                      <span className="text-[12px] font-mono opacity-40">
                        {data.date_after}
                      </span>
                      <div className="flex items-center gap-2 text-[12px] font-mono ml-auto">
                        {data.stats.added > 0 && (
                          <span className="text-[var(--diff-add-text)]">
                            +{data.stats.added}
                          </span>
                        )}
                        {data.stats.modified > 0 && (
                          <span className="text-[var(--diff-hunk-text)]">
                            ~{data.stats.modified}
                          </span>
                        )}
                        {data.stats.deleted > 0 && (
                          <span className="text-[var(--diff-del-text)]">
                            -{data.stats.deleted}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-[14px] opacity-60">
                      {data.pr_summary?.title ||
                        data.revision_after.amendment_law_title}
                    </p>
                  </div>
                  {/* Inline diff preview */}
                  {preview.length > 0 && (
                    <div className="border-t border-[var(--border)]">
                      {preview.map((line, i) => (
                        <DiffPreviewLine key={i} line={line} />
                      ))}
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {/* Life themes */}
      <section>
        <h2 className="text-[17px] font-bold mb-2">
          あなたの生活に関わる法律
        </h2>
        <p className="text-[13px] opacity-50 mb-4">
          気になるテーマから、関連する法律の改正履歴を確認できます
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {LIFE_THEMES.map((theme) => (
            <Link
              key={theme.id}
              href={`/theme/${theme.id}`}
              className="border border-[var(--border)] rounded-lg p-4 hover:bg-[var(--muted)] transition-colors"
            >
              <div className="mb-2 opacity-60">
                <Icon name={theme.icon} size={24} />
              </div>
              <div className="font-bold text-[14px]">{theme.label}</div>
              <div className="text-[12px] opacity-50 mt-1">
                {theme.description}
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* All laws */}
      <section>
        <h2 className="text-[17px] font-bold mb-4">法令一覧</h2>
        <div className="border border-[var(--border)] rounded-lg overflow-hidden">
          {timelines.map(({ id, data }, i) => (
            <Link
              key={id}
              href={`/law/${id}`}
              className={`flex items-center justify-between px-4 py-3 hover:bg-[var(--muted)] transition-colors ${
                i < timelines.length - 1
                  ? "border-b border-[var(--border)]"
                  : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon name="folder" size={16} className="opacity-30" />
                <span className="font-medium text-[14px]">
                  {data.law_title}
                </span>
              </div>
              <span className="text-[12px] font-mono opacity-50">
                {data.revision_count} commits
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
