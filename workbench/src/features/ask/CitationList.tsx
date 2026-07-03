import { useWorkbench } from "@/features/workbench/WorkbenchContext";
import { formatRelevance } from "@/lib/format";
import type { Citation } from "@/lib/api/types";

interface CitationListProps {
  citations: Citation[];
  grounded: boolean;
}

const DEFAULT_EXPANDED = 2;

function CitationItem({
  citation,
  onSelect,
}: {
  citation: Citation;
  onSelect: () => void;
}) {
  const pageLabel =
    citation.page != null ? `第 ${citation.page} 页` : "页码未知";

  const relevance = formatRelevance(citation.score);
  const relevanceKey = relevance === "高" ? "high" : relevance === "中" ? "mid" : "low";

  return (
    <button
      type="button"
      className="exam-citation-item"
      onClick={onSelect}
      aria-label={`引用 ${citation.source_file} ${pageLabel}`}
    >
      <div className="exam-citation-item__head">
        <span className="exam-citation-item__src">{citation.source_file}</span>
        <span className="exam-citation-item__page">{pageLabel}</span>
        <span
          className={`exam-citation-item__relevance exam-citation-item__relevance--${relevanceKey}`}
        >
          相关度：{relevance}
        </span>
      </div>
      <div className="exam-citation-item__snippet">{citation.snippet}</div>
    </button>
  );
}

export function CitationList({ citations, grounded }: CitationListProps) {
  const { setHighlightedSource, focusDocumentsPanel } = useWorkbench();

  if (citations.length === 0) return null;

  const expandedCount = grounded
    ? Math.min(DEFAULT_EXPANDED, citations.length)
    : 0;
  const expanded = citations.slice(0, expandedCount);
  const collapsed = citations.slice(expandedCount);

  const select = (source: string) => {
    setHighlightedSource(source);
    focusDocumentsPanel();
  };

  return (
    <div className="exam-citations">
      <p className="exam-citations__title">
        引用来源（{citations.length}）
        {grounded && expandedCount > 0 && (
          <span className="exam-citations__hint"> 点击可在左侧高亮对应资料</span>
        )}
      </p>

      {expanded.map((c, i) => (
        <CitationItem
          key={`exp-${c.source_file}-${i}`}
          citation={c}
          onSelect={() => select(c.source_file)}
        />
      ))}

      {collapsed.length > 0 && (
        <details className="exam-citations__more">
          <summary>查看更多引用（{collapsed.length}）</summary>
          {collapsed.map((c, i) => (
            <CitationItem
              key={`col-${c.source_file}-${i}`}
              citation={c}
              onSelect={() => select(c.source_file)}
            />
          ))}
        </details>
      )}
    </div>
  );
}
