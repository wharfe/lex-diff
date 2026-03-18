import Link from "next/link";
import { LIFE_THEMES, getThemeById } from "@/lib/life-themes";
import { getTimelineData } from "@/lib/data";
import { Icon } from "@/components/icon";

export function generateStaticParams() {
  return LIFE_THEMES.map((t) => ({ themeId: t.id }));
}

export default async function ThemePage({
  params,
}: {
  params: Promise<{ themeId: string }>;
}) {
  const { themeId } = await params;
  const theme = getThemeById(themeId);

  if (!theme) {
    return <div>テーマが見つかりません</div>;
  }

  // Load timeline data for each law in this theme
  const laws = theme.lawIds
    .map((id) => {
      try {
        return { id, data: getTimelineData(id) };
      } catch {
        return null;
      }
    })
    .filter((l): l is NonNullable<typeof l> => l !== null);

  return (
    <div className="space-y-6">
      {/* Theme header */}
      <div>
        <div className="flex items-center gap-2 text-[15px] mb-2">
          <Link href="/" className="opacity-50 hover:underline">
            lexdiff
          </Link>
          <span className="opacity-30">/</span>
          <span className="font-bold">{theme.label}</span>
        </div>

        <div className="border border-[var(--border)] rounded-lg p-4 md:p-6 bg-[var(--muted)]">
          <div className="flex items-center gap-3 mb-3">
            <Icon
              name={theme.icon}
              size={28}
              className="opacity-60"
            />
            <h1 className="text-[20px] font-bold">{theme.label}</h1>
          </div>
          <p className="text-[15px] leading-[26px] opacity-70">
            {theme.longDescription}
          </p>
          <p className="text-[13px] opacity-40 mt-3">
            関連する法令: {laws.length}件
          </p>
        </div>
      </div>

      {/* Law list */}
      <div className="space-y-4">
        {laws.map(({ id, data }) => {
          // Find the most recent diff for this law
          const recentWithDiff = data.timeline.find((e) => e.diff_id);

          return (
            <Link
              key={id}
              href={`/law/${id}`}
              className="block border border-[var(--border)] rounded-lg overflow-hidden hover:border-[var(--diff-hunk-text)]/50 transition-colors"
            >
              <div className="px-4 py-4 md:px-5">
                <div className="flex items-center gap-3 mb-1">
                  <Icon
                    name="folder"
                    size={16}
                    className="opacity-30"
                  />
                  <span className="text-[16px] font-bold">
                    {data.law_title}
                  </span>
                </div>

                {data.summary && (
                  <p className="text-[14px] leading-[24px] opacity-60 mt-2 ml-7">
                    {data.summary.description}
                  </p>
                )}

                <div className="flex items-center gap-4 mt-3 ml-7 text-[13px] flex-wrap">
                  <span className="flex items-center gap-1 opacity-50">
                    <Icon name="history" size={14} />
                    {data.revision_count} 回の改正
                  </span>
                  {data.contributors && data.contributors.length > 0 && (
                    <span className="flex items-center gap-1 opacity-50">
                      {data.contributors.length} contributors
                    </span>
                  )}
                  {recentWithDiff && (
                    <span className="text-[var(--diff-add-text)]">
                      最新の差分あり
                    </span>
                  )}
                </div>

                {data.summary?.keywords && (
                  <div className="flex flex-wrap gap-1.5 mt-3 ml-7">
                    {data.summary.keywords.slice(0, 5).map((kw) => (
                      <span
                        key={kw}
                        className="rounded-full bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] px-2 py-0.5 text-[11px]"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </Link>
          );
        })}
      </div>

      {/* Placeholder for future laws */}
      <div className="border border-dashed border-[var(--border)] rounded-lg p-6 text-center">
        <p className="text-[14px] opacity-40">
          今後、このテーマに関連する法令が追加されていきます
        </p>
      </div>
    </div>
  );
}
