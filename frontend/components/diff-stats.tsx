import { mainChangeCounts } from "@/lib/data";
import { LawDiffData } from "@/lib/types";
import { isPendingDiff } from "@/lib/pending";

export function DiffStats({ data }: { data: LawDiffData }) {
  // Counts come from mainChangeCounts so this badge, the home page and the
  // meta description can never disagree about the same amendment.
  const { total, added, modified, deleted, supplTotal } = mainChangeCounts(
    data.diffs
  );

  return (
    <div className="flex items-center gap-3 text-[13px] flex-wrap">
      <span className="font-medium">
        {isPendingDiff(data)
          ? total > 0
            ? `施行されると本則 ${total} 条が変わる`
            : "本則は変わらない"
          : total > 0
            ? `本則 ${total} 条が変更`
            : "本則の変更なし"}
      </span>
      {added > 0 && (
        <span className="text-[var(--diff-add-text)]">+{added} 追加</span>
      )}
      {modified > 0 && (
        <span className="text-[var(--diff-hunk-text)]">~{modified} 変更</span>
      )}
      {deleted > 0 && (
        <span className="text-[var(--diff-del-text)]">-{deleted} 削除</span>
      )}
      {supplTotal > 0 && (
        <span className="opacity-50">附則 {supplTotal} 件</span>
      )}
    </div>
  );
}
