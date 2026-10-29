import type { PublicCitation } from "@/lib/types";
import { cn } from "@/lib/utils";

type CitationChipProps = {
  index: number;
  citation: PublicCitation;
  selected: boolean;
  onSelect: (citation: PublicCitation) => void;
};

export function CitationChip({ index, citation, selected, onSelect }: CitationChipProps) {
  const pages =
    citation.pageStart == null
      ? "PDF"
      : citation.pageEnd != null && citation.pageEnd !== citation.pageStart
        ? `pp. ${citation.pageStart}-${citation.pageEnd}`
        : `p. ${citation.pageStart}`;
  const label = `Art. ${citation.articleNumber ?? "?"} § ${citation.section}`;

  return (
    <button
      type="button"
      onClick={() => onSelect(citation)}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border py-1 pr-3 pl-1 text-left text-xs",
        selected ? "border-ink bg-chip text-ink" : "border-rule bg-paper text-muted hover:text-ink",
      )}
    >
      <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-ink text-[0.65rem] text-paper">
        {index}
      </span>
      <span className="truncate">
        {label}, {pages}
      </span>
    </button>
  );
}
