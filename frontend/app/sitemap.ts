import type { MetadataRoute } from "next";
import {
  getDiffIds,
  getDiffData,
  getTimelineIds,
  getTimelineData,
  getArticleLawIds,
  getArticleData,
} from "@/lib/data";
import { LIFE_THEMES } from "@/lib/life-themes";
import { isEnforcedEntry, isPendingDiff } from "@/lib/pending";

export const dynamic = "force-static";

const BASE_URL = "https://lexdiff.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const diffIds = getDiffIds();
  const lawIds = getTimelineIds();
  const themeIds = LIFE_THEMES.map((t) => t.id);

  const diffs = diffIds.map((id) => ({ id, data: getDiffData(id) }));
  const pendingGeneratedOn = new Map(
    diffs.flatMap(({ id, data }) =>
      isPendingDiff(data) ? [[id, data.pending.generated_on] as const] : []
    )
  );

  // Compute the most recent diff date for the home page lastmod. A pending
  // diff's date is in the future (or a 政令 deadline): never a lastmod.
  const allDiffDates = diffs
    .filter(({ data }) => !isPendingDiff(data))
    .map(({ data }) => data.date_after);
  const latestDiffDate =
    allDiffDates.length > 0
      ? allDiffDates.sort().reverse()[0]
      : new Date().toISOString().slice(0, 10);

  return [
    // Static pages
    {
      url: BASE_URL,
      lastModified: latestDiffDate,
      changeFrequency: "weekly",
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/about`,
      changeFrequency: "monthly",
      priority: 0.5,
    },

    // Law pages (from timeline data)
    ...lawIds.map((id) => {
      const data = getTimelineData(id);
      // Timeline is sorted newest-first; the first enforced entry is the
      // lastmod (the very first was 2029-06-23 for 民法, a future date).
      const latestEntry = data.timeline.find((e) =>
        isEnforcedEntry(e, pendingGeneratedOn)
      );
      return {
        url: `${BASE_URL}/law/${id}`,
        lastModified: latestEntry?.enforcement_date,
        changeFrequency: "weekly" as const,
        priority: 0.8,
      };
    }),

    // Diff pages (from diff data files)
    ...diffs.map(({ id, data }) => {
      return {
        url: `${BASE_URL}/diff/${id}`,
        // When the page was built, not when the amendment takes effect.
        lastModified: isPendingDiff(data)
          ? data.pending.generated_on
          : data.date_after,
        changeFrequency: "monthly" as const,
        priority: 0.7,
      };
    }),

    // Theme pages (from life-themes config)
    ...themeIds.map((id) => ({
      url: `${BASE_URL}/theme/${id}`,
      lastModified: latestDiffDate,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),

    // Article pages (from articles data files)
    ...getArticleLawIds().flatMap((lawId) => {
      const data = getArticleData(lawId);
      return data.articles.map((a) => ({
        url: `${BASE_URL}/law/${lawId}/article/${a.slug}`,
        lastModified: data.source.asof,
        priority: 0.7,
      }));
    }),
  ];
}
