/** Hand-written search-intent overrides for /law/<lawId>.
 *
 * Why this lives in the frontend rather than in the timeline JSON: timeline.py
 * rebuilds `frontend/public/data/timelines/<lawId>.json` from scratch on every
 * run, so anything hand-written there is wiped on the next regeneration. These
 * are editorial decisions, not generated content, so they belong in source.
 *
 * What they fix (measured on 416AC0000000123, GSC 2026-06-10..09-07):
 *
 *   不動産登記法改正 履歴          51 imp   2.6位   9 clicks (CTR 17.6%)
 *   不動産登記法 改正             113 imp  12.2位   1 click
 *   不動産登記法改正               62 imp  11.8位   0 clicks
 *   不動産登記法 改正 わかりやすく  24 imp  13.3位   0 clicks
 *
 * The page ranks 2.6位 when the query says 履歴 and 12位 when it does not —
 * the default title (`…の改正履歴｜全N回の改正一覧`) matches only the first
 * shape. `titleHook` adds the words the losing queries actually use, and the
 * template keeps 改正履歴 in front so the one query that converts is not
 * traded away for the ones that might.
 *
 * Add an entry only when GSC shows the same page winning one query shape and
 * losing another. A guess here is worse than the default.
 *
 * Keep every fact out of these strings that the page already computes. The
 * first draft hard-coded 全24回 into the description while the title took the
 * count from `revision_count`, so the next amendment would have made one of the
 * two wrong — the same "facts belong in code, prose belongs to prose" rule
 * CLAUDE.md sets for the AI-written text.
 */
export interface LawSeoOverride {
  /** The amendment people are actually searching for, as they phrase it. */
  titleHook: string;
  /** Replaces the meta description. Lead with that amendment, not with the law. */
  description: string;
}

export const LAW_SEO_OVERRIDES: Record<string, LawSeoOverride> = {
  // 不動産登記法 — 2024-04-01 の相続登記義務化が検索の中心。
  //
  // 要件は条文どおりに書く。起算点は第76条の2第1項（相続開始を知り、かつ所有権を
  // 取得したことを知った日）、制裁は第164条（正当な理由がないのに怠ったとき、
  // 十万円以下の過料）。「相続を知った日から」「怠ると過料」と縮めると、どちらも
  // 条件の落ちた誤った説明になる — 廃止刑名の事故と同じ形の誤りで、しかもこれは
  // 手書きなので生成側の検証器では捕まらない。
  "416AC0000000123": {
    titleHook: "相続登記の義務化",
    description:
      "不動産登記法の改正をまとめました。2024年4月に始まった相続登記の義務化（相続の開始と所有権の取得を知った日から3年以内。正当な理由なく怠ると10万円以下の過料）を中心に、いつ・どの条文が・どう変わったかを改正履歴で確認できます。",
  },
};

export function lawSeo(lawId: string): LawSeoOverride | undefined {
  return LAW_SEO_OVERRIDES[lawId];
}

/** Throw if an override cannot apply. Called at build time from the /law page.
 *
 * These entries are hand-written and keyed by an opaque e-Gov id, so a typo
 * silently reverts a page that took months to rank — no error, just the default
 * title again. A blank titleHook is the same class of failure with a louder
 * symptom: the template would render `…の改正履歴｜から全N回の改正一覧まで`.
 * Failing the build is the only feedback that arrives before deployment.
 */
export function assertLawSeoOverridesValid(knownLawIds: string[]): void {
  const known = new Set(knownLawIds);
  for (const [lawId, override] of Object.entries(LAW_SEO_OVERRIDES)) {
    if (!known.has(lawId)) {
      throw new Error(
        `law-seo.ts: override for unknown law id "${lawId}" — no timeline data ships for it`,
      );
    }
    for (const field of ["titleHook", "description"] as const) {
      if (!override[field]?.trim()) {
        throw new Error(`law-seo.ts: override "${lawId}" has an empty ${field}`);
      }
    }
  }
}
