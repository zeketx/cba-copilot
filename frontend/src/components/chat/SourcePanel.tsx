import { useRef, useState, type PointerEvent } from "react";
import { Button } from "@/components/beautifui/Button";
import { FilingViewer } from "@/components/chat/FilingViewer";
import type { PublicCitation } from "@/lib/types";

type SourceView = "pdf" | "passage";

export function SourcePanel({
  citation,
  onClose,
}: {
  citation: PublicCitation | null;
  onClose: () => void;
}) {
  const [width, setWidth] = useState(440);
  const [passageViewFor, setPassageViewFor] = useState<string | null>(null);
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);
  if (citation === null) {
    return null;
  }
  const view: SourceView = passageViewFor === citation.passageId ? "passage" : "pdf";
  const setView = (next: SourceView) =>
    setPassageViewFor(next === "passage" ? citation.passageId : null);

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    drag.current = { startX: event.clientX, startWidth: width };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLButtonElement>) {
    if (drag.current === null) {
      return;
    }
    const next = drag.current.startWidth + (drag.current.startX - event.clientX);
    setWidth(Math.min(760, Math.max(280, next)));
  }

  return (
    <aside
      className="source-panel fixed inset-0 z-40 flex min-h-0 bg-surface pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]"
      style={{ ["--source-width" as string]: `${width}px` }}
    >
      <button
        type="button"
        aria-label="Resize source"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={() => {
          drag.current = null;
        }}
        className="source-resize hidden"
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[11px] tracking-wide text-ink-3 uppercase">Official source</p>
          <h2 className="text-base font-medium leading-snug break-words text-ink">{sourceSubtitle(citation)}</h2>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1">
          <Button
            type="button"
            variant={view === "pdf" ? "primary" : "quiet"}
            size="xs"
            aria-pressed={view === "pdf"}
            onClick={() => setView("pdf")}
          >
            PDF
          </Button>
          <Button
            type="button"
            variant={view === "passage" ? "primary" : "quiet"}
            size="xs"
            aria-pressed={view === "passage"}
            onClick={() => setView("passage")}
          >
            Passage
          </Button>
          <Button type="button" variant="quiet" size="xs" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
      {view === "pdf" ? (
        <iframe
          key={citation.sourceUrl}
          aria-label={pdfFrameTitle(citation)}
          src={citation.sourceUrl}
          className="h-full min-h-0 w-full flex-1 border-0 bg-white"
        />
      ) : (
        <FilingViewer
          html={wrapDocument(citation.sourceHtml)}
          placement={citation.placement}
          jumpNonce={0}
        />
      )}
      <a
        href={citation.sourceUrl}
        target="_blank"
        rel="noreferrer"
        className="border-t border-line px-4 py-2 text-[12px] text-ink-2 underline"
      >
        Open the official PDF page
      </a>
      </div>
    </aside>
  );
}

function viewerPageFromSourceUrl(sourceUrl: string): number | null {
  const match = /#page=(\d+)/i.exec(sourceUrl);
  if (match === null) {
    return null;
  }
  return Number(match[1]);
}

function sourceSubtitle(citation: PublicCitation): string {
  const pdfPage = viewerPageFromSourceUrl(citation.sourceUrl);
  if (pdfPage === null) {
    return citation.pageOrSection;
  }
  return `${citation.pageOrSection} · PDF p. ${pdfPage}`;
}

function pdfFrameTitle(citation: PublicCitation): string {
  const article =
    citation.articleNumber === null ? "CBA" : `Article ${citation.articleNumber}`;
  return `${article}, ${citation.section}, ${citation.pageOrSection}`;
}

function wrapDocument(body: string): string {
  return `<!doctype html><html><head><meta charset="utf-8"></head><body>${body}</body></html>`;
}
