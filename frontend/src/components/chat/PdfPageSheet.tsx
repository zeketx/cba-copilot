import type { PublicCitation } from "@/lib/types";

type PdfPageSheetProps = {
  citation: PublicCitation | null;
  onClose: () => void;
};

export function PdfPageSheet({ citation, onClose }: PdfPageSheetProps) {
  if (citation == null) {
    return null;
  }

  return (
    <aside className="fixed inset-x-0 bottom-0 z-20 flex max-h-[70vh] flex-col border-t border-rule bg-paper shadow-lg md:static md:max-h-none md:w-[28rem] md:border-t-0 md:border-l">
      <div className="flex items-start justify-between gap-3 border-b border-rule px-4 py-3">
        <div>
          <p className="text-xs tracking-wide text-muted uppercase">Official PDF</p>
          <h2 className="font-serif text-lg leading-snug">
            Article {citation.articleNumber} § {citation.section}
          </h2>
        </div>
        <button type="button" onClick={onClose} className="text-sm text-muted hover:text-ink">
          Close
        </button>
      </div>
      <p className="px-4 py-3 text-sm leading-relaxed text-ink">{citation.excerpt}</p>
      <a
        href={citation.sourceUrl}
        target="_blank"
        rel="noreferrer"
        className="px-4 pb-3 text-sm underline"
      >
        Open this page in the official PDF
      </a>
      <iframe
        title={`CBA page ${citation.pageStart ?? ""}`}
        src={citation.sourceUrl}
        className="min-h-64 w-full flex-1 border-0 bg-white"
      />
    </aside>
  );
}
