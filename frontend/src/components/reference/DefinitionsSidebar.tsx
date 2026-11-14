import { Button } from "@/components/beautifui/Button";
import { citationLabel, pdfPageUrl, type DefinitionEntry } from "@/lib/definitions";
import { cn } from "@/lib/utils";

type DefinitionsSidebarProps = {
  status: string;
  entries: DefinitionEntry[];
  open: boolean;
  /** Hide the desktop column, e.g. while the source viewer needs the room. */
  collapsed?: boolean;
  onClose: () => void;
};

export function DefinitionsSidebar({
  status,
  entries,
  open,
  collapsed = false,
  onClose,
}: DefinitionsSidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-0 z-30 overflow-y-auto bg-surface p-4 md:static md:z-0 md:w-80 md:shrink-0 md:border-l md:border-line",
        open ? "block" : "hidden",
        collapsed ? "md:hidden" : "md:block",
      )}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] tracking-wide text-ink-3 uppercase">{status}</p>
          <h2 className="text-lg font-semibold text-ink">Plain-English reference</h2>
        </div>
        <Button type="button" variant="quiet" size="xs" className="md:hidden" onClick={onClose}>
          Close
        </Button>
      </div>
      <ul className="space-y-4">
        {entries.map((entry) => (
          <li key={entry.term} className="border-b border-line pb-4">
            <h3 className="text-[13px] font-medium text-ink">{entry.term}</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{entry.definition}</p>
            <a
              className="mt-2 inline-block text-[12px] text-ink-3 underline"
              href={pdfPageUrl(entry.citation.page_start)}
              target="_blank"
              rel="noreferrer"
            >
              {citationLabel(
                entry.citation.article,
                entry.citation.section,
                entry.citation.page_start,
                entry.citation.page_end,
              )}
              {entry.citation.verified ? "" : " (unverified)"}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
