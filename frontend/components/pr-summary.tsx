import { PrSummary } from "@/lib/types";
import { Icon } from "./icon";

export function PrSummaryCard({ summary }: { summary: PrSummary }) {
  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="bg-[var(--muted)] px-4 py-3 border-b border-[var(--border)] flex items-center gap-2">
        <Icon name="description" size={16} className="opacity-50" />
        <span className="text-[13px] font-medium opacity-70">
          改正の概要
        </span>
        <h2 className="text-[17px] font-bold">{summary.title}</h2>
      </div>
      <div className="p-4 md:p-5 space-y-5">
        <p className="text-[15px] leading-[26px]">{summary.summary}</p>

        <div>
          <h3 className="text-[14px] font-bold mb-3 opacity-70">
            主な変更点
          </h3>
          <div className="space-y-4">
            {summary.key_changes.map((change, i) => (
              <div
                key={i}
                className="border-l-2 border-[var(--diff-hunk-text)] pl-4"
              >
                <span className="text-[14px] font-bold text-[var(--diff-hunk-text)]">
                  {change.theme}
                </span>
                <p className="text-[14px] mt-1 leading-[24px]">
                  {change.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[var(--diff-add-bg)] rounded-lg p-4">
            <h3 className="text-[13px] font-bold text-[var(--diff-add-text)] mb-2">
              国民生活への影響
            </h3>
            <p className="text-[14px] leading-[24px]">{summary.impact}</p>
          </div>
          <div className="bg-[var(--diff-hunk-bg)] rounded-lg p-4">
            <h3 className="text-[13px] font-bold text-[var(--diff-hunk-text)] mb-2">
              改正の背景
            </h3>
            <p className="text-[14px] leading-[24px]">{summary.background}</p>
          </div>
        </div>

        <p className="text-[13px] leading-[22px] opacity-50 pt-3 border-t border-[var(--border)] flex items-start gap-1.5">
          <Icon name="smart_toy" size={14} className="shrink-0 mt-1" />
          <span>
            この概要はClaude
            AI（Anthropic社）により自動生成されています。
            誤りや省略が含まれる可能性があります。正確な内容はe-Gov法令検索の原文をご確認ください。
          </span>
        </p>
      </div>
    </div>
  );
}
