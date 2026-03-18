import { Icon } from "./icon";
import { OpenGikaiMapping } from "@/lib/data";

export function OpenGikaiLinks({
  mapping,
}: {
  mapping: OpenGikaiMapping;
}) {
  if (!mapping.threads.length) return null;

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] flex items-center gap-2 text-[14px] font-medium">
        <Icon name="gavel" size={16} className="opacity-40" />
        国会での審議（OpenGIKAI）
      </div>
      <div className="px-4 py-3 space-y-2">
        {mapping.threads.map((thread) => (
          <a
            key={thread.thread_id}
            href={thread.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-3 rounded-lg p-2 -mx-2 hover:bg-[var(--muted)] transition-colors"
          >
            <div className="min-w-0 flex-1">
              <div className="text-[14px] font-medium text-[var(--diff-hunk-text)]">
                {thread.title}
                <Icon
                  name="open_in_new"
                  size={12}
                  className="ml-1 opacity-50"
                />
              </div>
              <div className="text-[12px] opacity-50 mt-0.5">
                {thread.date} · {thread.committee}
              </div>
            </div>
          </a>
        ))}
        <p className="text-[11px] opacity-30 pt-1">
          OpenGIKAIで審議の詳細を確認できます
        </p>
      </div>
    </div>
  );
}
