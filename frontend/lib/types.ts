export interface Paragraph {
  num: string;
  text: string;
}

export interface CrossReference {
  ref: string;
  article_num: string;
  context: string;
}

export interface ArticleAnnotation {
  plain_summary: string;
  change_description: string;
  cross_references: CrossReference[];
}

export interface ArticleDiff {
  type: "added" | "modified" | "deleted";
  article_num: string;
  title_before: string | null;
  title_after: string | null;
  lines_before: string[];
  lines_after: string[];
  diff: string[];
  paragraphs_before: Paragraph[];
  paragraphs_after: Paragraph[];
  section_path: string[];
  annotation?: ArticleAnnotation;
}

export interface KeyChange {
  theme: string;
  description: string;
}

export interface PrSummary {
  title: string;
  summary: string;
  key_changes: KeyChange[];
  impact: string;
  background: string;
}

export interface RevisionInfo {
  law_revision_id: string;
  amendment_law_title: string;
  amendment_enforcement_date: string;
}

export interface LawDiffData {
  law_id: string;
  law_title: string;
  date_before: string;
  date_after: string;
  revision_before: RevisionInfo;
  revision_after: RevisionInfo;
  stats: {
    added: number;
    modified: number;
    deleted: number;
  };
  diffs: ArticleDiff[];
  pr_summary?: PrSummary;
}

// Timeline types

export interface TimelineEntry {
  enforcement_date: string;
  promulgate_date: string;
  amendment_law_title: string;
  law_revision_id: string;
  diff_id: string | null;
}

export interface LawTimeline {
  law_id: string;
  law_title: string;
  law_num: string;
  promulgation_date: string;
  revision_count: number;
  timeline: TimelineEntry[];
}
