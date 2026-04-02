import type { MetadataRoute } from "next";
import {
  getDiffIds,
  getDiffData,
  getTimelineIds,
  getTimelineData,
} from "@/lib/data";
import { LIFE_THEMES } from "@/lib/life-themes";

export const dynamic = "force-static";

const BASE_URL = "https://lexdiff.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const diffIds = getDiffIds();
  const lawIds = getTimelineIds();
  const themeIds = LIFE_THEMES.map((t) => t.id);

  // Compute the most recent diff date for the home page lastmod
  const allDiffDates = diffIds.map((id) => getDiffData(id).date_after);
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
      // Timeline is sorted newest-first; use the first entry as lastmod
      const latestEntry = data.timeline[0];
      return {
        url: `${BASE_URL}/law/${id}`,
        lastModified: latestEntry?.enforcement_date,
        changeFrequency: "weekly" as const,
        priority: 0.8,
      };
    }),

    // Diff pages (from diff data files)
    ...diffIds.map((id) => {
      const data = getDiffData(id);
      return {
        url: `${BASE_URL}/diff/${id}`,
        lastModified: data.date_after,
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
  ];
}
