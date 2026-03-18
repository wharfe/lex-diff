import Link from "next/link";
import {
  getDiffIds,
  getDiffData,
  getTimelineIds,
  getTimelineData,
} from "@/lib/data";
import { LIFE_THEMES } from "@/lib/life-themes";
import { Icon } from "@/components/icon";

export default function Home() {
  const timelineIds = getTimelineIds();
  const timelines = timelineIds.map((id) => ({
    id,
    data: getTimelineData(id),
  }));

  const diffIds = getDiffIds();
  const diffs = diffIds.map((id) => ({ id, data: getDiffData(id) }));

  return (
    <div className="space-y-10">
      {/* Life themes */}
      <section>
        <h2 className="text-xl font-bold mb-2">あなたの生活に関わる法律</h2>
        <p className="text-sm opacity-50 mb-4">
          気になるテーマから、関連する法律の改正履歴を確認できます
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {LIFE_THEMES.map((theme) => (
            <Link
              key={theme.id}
              href={`/law/${theme.lawIds[0]}`}
              className="border border-[var(--border)] rounded-lg p-4 hover:bg-[var(--muted)] transition-colors"
            >
              <div className="mb-2 opacity-60">
                <Icon name={theme.icon} size={28} />
              </div>
              <div className="font-bold text-sm">{theme.label}</div>
              <div className="text-xs opacity-50 mt-1">
                {theme.description}
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Recent diffs */}
      {diffs.length > 0 && (
        <section>
          <h2 className="text-xl font-bold mb-4">
            <Icon name="difference" size={20} className="opacity-50 mr-1" />
            最近の改正
          </h2>
          <div className="grid gap-4">
            {diffs.map(({ id, data }) => (
              <Link
                key={id}
                href={`/diff/${encodeURIComponent(id)}`}
                className="block border border-[var(--border)] rounded-lg p-5 hover:bg-[var(--muted)] transition-colors"
              >
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-lg font-bold">{data.law_title}</span>
                  <span className="text-xs font-mono opacity-50">
                    {data.date_before} &rarr; {data.date_after}
                  </span>
                </div>
                {data.pr_summary ? (
                  <p className="text-sm opacity-70 mb-3">
                    {data.pr_summary.title}
                  </p>
                ) : (
                  <p className="text-sm opacity-70 mb-3">
                    {data.revision_after.amendment_law_title}
                  </p>
                )}
                <div className="flex items-center gap-3 text-xs font-mono">
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
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* All laws */}
      <section>
        <h2 className="text-xl font-bold mb-4">
          <Icon name="gavel" size={20} className="opacity-50 mr-1" />
          法令一覧
        </h2>
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
                <span className="font-medium">{data.law_title}</span>
              </div>
              <span className="text-xs font-mono opacity-50">
                {data.revision_count} commits
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
