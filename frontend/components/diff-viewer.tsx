"use client";

import { useState } from "react";
import { ArticleDiff } from "@/lib/types";

function DiffLine({ line }: { line: string }) {
  const isAdd = line.startsWith("+") && !line.startsWith("+++");
  const isDel = line.startsWith("-") && !line.startsWith("---");
  const isHunk = line.startsWith("@@");
  const isMeta = line.startsWith("---") || line.startsWith("+++");

  if (isMeta) return null;

  let className =
    "px-4 py-1 font-mono text-[13px] leading-[22px] whitespace-pre-wrap ";
  let prefix = " ";

  if (isAdd) {
    className += "bg-[var(--diff-add-bg)] text-[var(--diff-add-text)]";
    prefix = "+";
  } else if (isDel) {
    className += "bg-[var(--diff-del-bg)] text-[var(--diff-del-text)]";
    prefix = "-";
  } else if (isHunk) {
    className +=
      "bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] py-1.5";
    prefix = "";
  } else {
    className += "text-[var(--foreground)]";
  }

  const content = isAdd || isDel ? line.slice(1) : line;

  return (
    <div className={className}>
      <span className="inline-block w-5 select-none opacity-50 text-right mr-2">
        {prefix}
      </span>
      {content}
    </div>
  );
}

function TypeBadge({ type }: { type: ArticleDiff["type"] }) {
  const styles = {
    added: "bg-[var(--diff-add-bg)] text-[var(--diff-add-text)]",
    modified: "bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)]",
    deleted: "bg-[var(--diff-del-bg)] text-[var(--diff-del-text)]",
  };
  const labels = {
    added: "追加",
    modified: "変更",
    deleted: "削除",
  };

  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-[12px] font-medium ${styles[type]}`}
    >
      {labels[type]}
    </span>
  );
}

function AnnotationCard({ diff }: { diff: ArticleDiff }) {
  const { annotation } = diff;
  if (!annotation) return null;

  return (
    <div className="bg-[var(--muted)] border-b border-[var(--border)] px-4 py-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        {annotation.plain_summary && (
          <p className="text-[15px] font-medium leading-[24px]">
            {annotation.plain_summary}
          </p>
        )}
        <span className="text-[11px] opacity-40 shrink-0 mt-0.5">
          AI要約
        </span>
      </div>
      {annotation.change_description && (
        <p className="text-[14px] leading-[24px] opacity-80">
          {annotation.change_description}
        </p>
      )}
      {annotation.cross_references?.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {annotation.cross_references.map((ref, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 text-[12px] bg-[var(--diff-hunk-bg)] text-[var(--diff-hunk-text)] rounded px-2 py-1"
              title={ref.context}
            >
              {ref.ref}
              <span className="opacity-60 hidden md:inline">
                — {ref.context}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ArticleDiffCard({ diff }: { diff: ArticleDiff }) {
  const [expanded, setExpanded] = useState(true);
  const title = diff.title_after || diff.title_before || "";
  const sectionLabel = diff.section_path.join("/");

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-3 bg-[var(--muted)] hover:bg-[var(--muted)]/80 text-left cursor-pointer"
      >
        <span className="text-[13px] opacity-50 shrink-0">
          {expanded ? "▾" : "▸"}
        </span>
        <TypeBadge type={diff.type} />
        {sectionLabel && (
          <span className="text-[13px] font-mono opacity-40 hidden md:inline">
            {sectionLabel}/
          </span>
        )}
        <span className="font-mono font-medium text-[14px]">{title}</span>
        {diff.annotation?.plain_summary && (
          <span className="text-[13px] opacity-50 hidden lg:inline ml-2">
            — {diff.annotation.plain_summary}
          </span>
        )}
      </button>
      {expanded && (
        <div className="border-t border-[var(--border)]">
          <AnnotationCard diff={diff} />
          {diff.diff.map((line, i) => (
            <DiffLine key={i} line={line} />
          ))}
        </div>
      )}
    </div>
  );
}

export function DiffViewer({ diffs }: { diffs: ArticleDiff[] }) {
  return (
    <div className="flex flex-col gap-5">
      {diffs.map((diff) => (
        <ArticleDiffCard key={diff.article_num} diff={diff} />
      ))}
    </div>
  );
}
