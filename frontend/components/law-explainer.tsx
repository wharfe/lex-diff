import { Icon } from "@/components/icon";
import type { LawExplainer } from "@/lib/types";

export function LawExplainerSection({
  lawTitle,
  explainer,
}: {
  lawTitle: string;
  explainer: LawExplainer;
}) {
  return (
    <section className="border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-[var(--muted)] border-b border-[var(--border)] flex items-center gap-2">
        <Icon name="history" size={16} className="opacity-40" />
        <h2 className="text-[15px] font-medium">
          {lawTitle}の最近の改正をわかりやすく
        </h2>
        <span className="text-[11px] opacity-40 ml-auto">AI要約</span>
      </div>
      <div className="px-4 py-4 space-y-5">
        <p className="text-[15px] leading-[26px]">{explainer.intro}</p>

        <div className="space-y-4">
          {explainer.recent_changes.map((c, i) => (
            <div
              key={i}
              className="border-t border-[var(--border)] pt-4 first:border-t-0 first:pt-0"
            >
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-mono text-[13px] text-[var(--diff-hunk-text)]">
                  {c.year}
                </span>
                <h3 className="text-[15px] font-bold">{c.title}</h3>
              </div>
              <dl className="space-y-1.5 text-[14px] leading-[24px]">
                <div>
                  <dt className="inline font-medium">何が変わった？ </dt>
                  <dd className="inline opacity-70">{c.what}</dd>
                </div>
                {c.why && (
                  <div>
                    <dt className="inline font-medium">なぜ変わった？ </dt>
                    <dd className="inline opacity-70">{c.why}</dd>
                  </div>
                )}
                {c.impact && (
                  <div>
                    <dt className="inline font-medium">私たちへの影響 </dt>
                    <dd className="inline opacity-70">{c.impact}</dd>
                  </div>
                )}
              </dl>
            </div>
          ))}
        </div>

        {explainer.faq.length > 0 && (
          <div className="pt-2">
            <h3 className="text-[14px] font-medium mb-3">よくある質問</h3>
            <div className="space-y-3">
              {explainer.faq.map((f, i) => (
                <div key={i}>
                  <p className="text-[14px] font-bold">Q. {f.q}</p>
                  <p className="text-[14px] leading-[24px] opacity-70 mt-0.5">
                    A. {f.a}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
