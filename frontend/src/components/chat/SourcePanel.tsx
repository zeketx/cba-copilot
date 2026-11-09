import { useRef, useState, type PointerEvent } from "react";
import { Button } from "@/components/beautifui/Button";
import { FilingViewer } from "@/components/chat/FilingViewer";
import type { PublicCitation } from "@/lib/types";

export function SourcePanel({
  citation,
  onClose,
}: {
  citation: PublicCitation | null;
  onClose: () => void;
}) {
  const [width, setWidth] = useState(440);
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);
  if (citation === null) {
    return null;
  }

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
      className="source-panel fixed inset-0 z-20 flex min-h-0 bg-surface"
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
      <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <p className="font-mono text-[11px] tracking-wide text-ink-3 uppercase">Official source</p>
          <h2 className="text-base font-medium leading-snug text-ink">{citation.pageOrSection}</h2>
        </div>
        <Button type="button" variant="quiet" size="xs" onClick={onClose}>
          Close
        </Button>
      </div>
      <FilingViewer
        html={wrapDocument(citation.sourceHtml)}
        placement={citation.placement}
        jumpNonce={0}
      />
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

function wrapDocument(body: string): string {
  return `<!doctype html><html><head><meta charset="utf-8"></head><body>${body}</body></html>`;
}
