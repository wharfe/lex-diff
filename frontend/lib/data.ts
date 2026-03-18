import { LawDiffData, LawTimeline } from "./types";
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
