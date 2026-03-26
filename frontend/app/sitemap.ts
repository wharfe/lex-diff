import type { MetadataRoute } from "next";
import { getDiffIds, getTimelineIds } from "@/lib/data";
import { LIFE_THEMES } from "@/lib/life-themes";

export const dynamic = "force-static";

const BASE_URL = "https://lexdiff.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const diffIds = getDiffIds();
  const lawIds = getTimelineIds();
  const themeIds = LIFE_THEMES.map((t) => t.id);

  return [
    // Static pages
    { url: BASE_URL, changeFrequency: "weekly", priority: 1.0 },
    { url: `${BASE_URL}/about`, changeFrequency: "monthly", priority: 0.5 },

    // Law pages (from timeline data)
    ...lawIds.map((id) => ({
      url: `${BASE_URL}/law/${id}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),

    // Diff pages (from diff data files)
    ...diffIds.map((id) => ({
      url: `${BASE_URL}/diff/${id}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),

    // Theme pages (from life-themes config)
    ...themeIds.map((id) => ({
      url: `${BASE_URL}/theme/${id}`,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
  ];
}
