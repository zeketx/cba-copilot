import { citationLabel, pdfPageUrl, type DefinitionEntry } from "@/lib/definitions";
import { cn } from "@/lib/utils";

type DefinitionsSidebarProps = {
  status: string;
  entries: DefinitionEntry[];
  open: boolean;
  onClose: () => void;
};

export function DefinitionsSidebar({ status, entries, open, onClose }: DefinitionsSidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-0 z-30 overflow-y-auto bg-paper p-4 md:static md:z-0 md:block md:w-80 md:border-l md:border-rule",
        open ? "block" : "hidden md:block",
      )}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs tracking-wide text-muted uppercase">{status}</p>
          <h2 className="font-serif text-xl">Plain-English reference</h2>
        </div>
        <button type="button" className="text-sm text-muted md:hidden" onClick={onClose}>
          Close
        </button>
      </div>
      <ul className="space-y-4">
        {entries.map((entry) => (
          <li key={entry.term} className="border-b border-rule pb-4">
            <h3 className="font-medium">{entry.term}</h3>
            <p className="mt-1 text-sm leading-relaxed text-ink">{entry.definition}</p>
            <a
              className="mt-2 inline-block text-xs text-muted underline"
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
