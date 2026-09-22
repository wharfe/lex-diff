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
  /** True when this entry is a 附則 (supplementary provision) of the amending
   * law rather than an article of the main text. e-Gov numbers 附則
   * independently, so its article_num is namespaced
   * "suppl_<AmendLawNum>_<num>" (see suppl_key in scripts/diff.py). */
  is_suppl?: boolean;
  /** The amending law a 附則 belongs to, e.g. "令和五年六月二三日法律第六六号". */
  amend_law_num?: string | null;
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
  /** added/modified/deleted count 本則 only; `suppl` is how many 附則 entries
   *  there are. Nothing in the app reads this — it is the published JSON's shape. */
  stats: {
    added: number;
    modified: number;
    deleted: number;
    main: number;
    suppl: number;
  };
  diffs: ArticleDiff[];
  pr_summary?: PrSummary;
  proposer?: Proposer;
}

// Proposer types

export interface Minister {
  name: string;
  position: string;
  party: string | null;
}

export interface Proposer {
  submission_type: string | null;
  minister: Minister | null;
  committee: string | null;
}

// Timeline types

export interface TimelineEntry {
  enforcement_date: string;
  promulgate_date: string;
  amendment_law_title: string;
  law_revision_id: string;
  diff_id: string | null;
  proposer?: Proposer;
}

export interface LawSummary {
  description: string;
  scope: string;
  keywords: string[];
}

export interface ExplainerChange {
  year: string;
  title: string;
  what: string;
  why?: string;
  impact?: string;
  grounded: boolean;
}

export interface ExplainerFaq {
  q: string;
  a: string;
}

export interface LawExplainer {
  intro: string;
  recent_changes: ExplainerChange[];
  faq: ExplainerFaq[];
}

export interface Contributor {
  name: string;
  position: string;
  party: string | null;
  count: number;
}

export interface LawTimeline {
  law_id: string;
  law_title: string;
  law_num: string;
  promulgation_date: string;
  revision_count: number;
  timeline: TimelineEntry[];
  summary?: LawSummary;
  category?: string;
  contributors?: Contributor[];
  explainer?: LawExplainer;
}

// Article page types

export interface ArticleSource {
  asof: string;
  fetched_at: string;
  law_revision_id: string;
  amendment_enforcement_date: string;
}

/** A paragraph of today's text. `mark` is what the printed law shows in the
 *  margin ("" for the first paragraph, "２" onward); `num` is what a citation
 *  uses. Both come from the Article node, not from a position counter. */
export interface ArticleParagraph extends Paragraph {
  mark: string;
}

/** current.status has three values, not two: an article can be repealed
 *  standalone ("deleted") or folded into a range node that replaced it
 *  ("merged_deleted"). The two need different sentences on the page -- a
 *  standalone repeal was folded into nothing, so the 欠番 wording used for
 *  merged_deleted would be false for it. TOMBSTONE_STATUSES / isTombstone
 *  below are the one place that draws this line; nothing else compares
 *  against a bare status string. Mirrors scripts/articles.py's
 *  TOMBSTONE_STATUSES. */
export const TOMBSTONE_STATUSES = ["deleted", "merged_deleted"] as const;

export type TombstoneStatus = (typeof TOMBSTONE_STATUSES)[number];

export function isTombstone(status: CurrentText["status"]): status is TombstoneStatus {
  return (TOMBSTONE_STATUSES as readonly string[]).includes(status);
}

export interface CurrentText {
  status: "present" | "deleted" | "merged_deleted";
  source_article_num: string;
  source_label: string;
  paragraphs: ArticleParagraph[];
}

export interface FormerText {
  as_of: string;
  label: string;
  paragraphs: Paragraph[];
}

/** Present only when the article's text has not moved on since the note was
 *  written. null is the normal outcome for an article amended again since. */
export interface CurrentSummary {
  text: string;
  evidence_date: string;
}

export interface ArticleChange {
  diff_id: string;
  enforcement_date: string;
  year: string;
  type: "added" | "modified" | "deleted";
  amendment_law_title: string;
  /** Which side of this amendment `plain_summary` describes, decided in Python
   *  on that entry's own post-amendment text (scripts/articles.py's
   *  summary_basis). Not derivable from `type` here: e-Gov records some
   *  repeals as a modification whose new body is the single word 削除, so
   *  民法733/746 and 刑法178 are "modified" with nothing standing after them.
   *  Render from this field; never branch on `type` for the time label. */
  summary_basis: "before" | "after";
  change_description: string;
  plain_summary: string;
  /** Shown as text on the history card, never as links: a reference written
   *  about an older version of this article may point at a moved provision. */
  cross_references: { ref: string; context: string }[];
}

export interface RelatedArticle {
  ref: string;
  article_num: string;
  context: string;
  slug: string | null;
  has_page: boolean;
}

export interface ArticlePage {
  article_num: string;
  slug: string;
  display_num: string;
  label: string;
  caption: string;
  section_path: string[];
  current: CurrentText;
  current_summary: CurrentSummary | null;
  former: FormerText | null;
  changes: ArticleChange[];
  related_articles: RelatedArticle[];
}

export interface LawArticles {
  law_id: string;
  law_title: string;
  source: ArticleSource;
  articles: ArticlePage[];
}
