import { LawDiffData } from "@/lib/types";

export function DiffStats({ data }: { data: LawDiffData }) {
  const { stats } = data;
  const total = stats.added + stats.modified + stats.deleted;

  return (
    <div className="flex items-center gap-3 text-[13px] flex-wrap">
      <span className="font-medium">{total} 条が変更</span>
      {stats.added > 0 && (
        <span className="text-[var(--diff-add-text)]">+{stats.added} 追加</span>
      )}
      {stats.modified > 0 && (
        <span className="text-[var(--diff-hunk-text)]">
          ~{stats.modified} 変更
        </span>
      )}
      {stats.deleted > 0 && (
        <span className="text-[var(--diff-del-text)]">
          -{stats.deleted} 削除
        </span>
      )}
    </div>
  );
}
