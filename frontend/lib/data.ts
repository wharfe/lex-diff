import { ArticleDiff, LawDiffData, LawTimeline } from "./types";
import fs from "fs";
import path from "path";

const DATA_DIR = path.join(process.cwd(), "public", "data");
const TIMELINE_DIR = path.join(DATA_DIR, "timelines");

export function getDiffIds(): string[] {
  const files = fs.readdirSync(DATA_DIR);
  return files
    .filter(
      (f) =>
        f.endsWith(".json") &&
        !f.includes("index") &&
        !f.includes("mapping")
    )
    .map((f) => f.replace(".json", ""));
}

export function getDiffData(diffId: string): LawDiffData {
  const filePath = path.join(DATA_DIR, `${diffId}.json`);
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as LawDiffData;
}

export function getTimelineIds(): string[] {
  if (!fs.existsSync(TIMELINE_DIR)) return [];
  const files = fs.readdirSync(TIMELINE_DIR);
  return files
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(".json", ""));
}

export function getTimelineData(lawId: string): LawTimeline {
  const filePath = path.join(TIMELINE_DIR, `${lawId}.json`);
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as LawTimeline;
}

export interface OpenGikaiThread {
  thread_id: string;
  title: string;
  url: string;
  date: string;
  committee: string;
}

export interface OpenGikaiMapping {
  law_title: string;
  threads: OpenGikaiThread[];
}

export function getOpenGikaiLinks(
  lawId: string
): OpenGikaiMapping | null {
  const mappingPath = path.join(DATA_DIR, "opengikai-mapping.json");
  if (!fs.existsSync(mappingPath)) return null;
  const raw = fs.readFileSync(mappingPath, "utf-8");
  const mapping = JSON.parse(raw) as Record<string, OpenGikaiMapping>;
  return mapping[lawId] || null;
}

/** Counts of 本則 changes only.
 *
 * `stats.added/modified/deleted` include 附則, whose articles are numbered
 * separately from the main text — folding them in claimed "2 条が変更" for an
 * amendment that touched no article of the main text at all. Every surface
 * that shows a change count goes through this.
 */
export function mainChangeCounts(diffs: ArticleDiff[]) {
  const main = diffs.filter((d) => !d.is_suppl);
  const count = (type: ArticleDiff["type"]) =>
    main.filter((d) => d.type === type).length;
  return {
    total: main.length,
    added: count("added"),
    modified: count("modified"),
    deleted: count("deleted"),
    supplTotal: diffs.length - main.length,
  };
}

/** The 本則 entry best suited to preview an amendment, or null.
 *
 * 附則 is excluded: previewing 附則第一条 as if it were the substance of the
 * amendment is the same mistake as counting it — a card can otherwise say
 * "附則のみ" and then show a 施行期日 paragraph as what changed.
 */
export function previewDiff(diffs: ArticleDiff[]): ArticleDiff | null {
  const main = diffs.filter((d) => !d.is_suppl);
  const withBothSides = main.find(
    (d) =>
      d.type === "modified" &&
      d.diff.some((l) => l.startsWith("+") && !l.startsWith("+++")) &&
      d.diff.some((l) => l.startsWith("-") && !l.startsWith("---"))
  );
  return withBothSides ?? main.find((d) => d.type === "modified") ?? null;
}
