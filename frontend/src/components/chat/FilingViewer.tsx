import { useEffect, useRef } from "react";
import type { FilingPlacement } from "@/lib/citation";
import { FILING_IFRAME_SANDBOX } from "@/lib/source-url";

const DOCUMENT_STYLE = `
html { scroll-behavior: auto; }
body {
  margin: 0;
  padding: 24px;
  background: #fff;
  color: #1c1917;
  font: 15px/1.6 Georgia, "Iowan Old Style", serif;
}
h2, h3, p { max-width: 72ch; margin-left: auto; margin-right: auto; }
h2 { font-size: 18px; margin-top: 1.6em; }
h3 { font-size: 15px; color: #57534e; }
@property --filing-mark { syntax: "<color>"; inherits: true; initial-value: transparent; }
@property --filing-edge { syntax: "<color>"; inherits: true; initial-value: transparent; }
.filing-passage { box-shadow: inset 3px 0 0 #d97706; }
mark.filing-cite { background-color: #fde68a; }
html.filing-anchored {
  --filing-mark: #fde68a;
  --filing-edge: #d97706;
  animation: filing-mark-in 320ms ease-out both;
}
@keyframes filing-mark-in {
  from { --filing-mark: transparent; --filing-edge: transparent; }
  to { --filing-mark: #fde68a; --filing-edge: #d97706; }
}
@media (prefers-reduced-motion: reduce) {
  html.filing-anchored { animation: none; }
}
@media (max-width: 430px) {
  body { padding: 12px; }
}
`;

export function FilingViewer({
  html,
  placement,
  jumpNonce,
}: {
  html: string;
  placement: FilingPlacement;
  jumpNonce: number;
}) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);

  useEffect(() => {
    const frame = frameRef.current;
    if (frame === null) {
      return;
    }
    const built = highlightedDocument(html, placement);
    const blob = new Blob([built.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    frame.src = built.anchorId === null ? url : `${url}#${built.anchorId}`;
    return () => {
      URL.revokeObjectURL(url);
      frame.removeAttribute("src");
    };
  }, [html, placement, jumpNonce]);

  return (
    <iframe
      ref={frameRef}
      aria-label="CBA source"
      sandbox={FILING_IFRAME_SANDBOX}
      className="h-full min-h-0 w-full flex-1 border-0 bg-white"
    />
  );
}

function highlightedDocument(
  html: string,
  placement: FilingPlacement,
): { html: string; anchorId: string | null } {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const located = paintFiling(doc, placement);
  const anchorId = located?.anchor.id ? located.anchor.id : null;
  return { html: `<!doctype html>${doc.documentElement.outerHTML}`, anchorId };
}

function paintFiling(
  doc: Document,
  placement: FilingPlacement,
): { range: Range; anchor: Element } | null {
  ensureStyle(doc);
  clearHighlight(doc);
  const located = placement.kind === "miss" ? null : locate(doc, placement);
  const root = doc.documentElement;
  if (located === null) {
    root.classList.remove("filing-anchored");
    return null;
  }
  const block = passageOf(located.range);
  block?.classList.add("filing-passage");
  markRange(doc, located.range);
  root.classList.add("filing-anchored");
  return located;
}

function ensureStyle(doc: Document) {
  if (doc.getElementById("filing-layout-style") !== null) {
    return;
  }
  const style = doc.createElement("style");
  style.id = "filing-layout-style";
  style.textContent = DOCUMENT_STYLE;
  (doc.head ?? doc.documentElement).appendChild(style);
}

function clearHighlight(doc: Document) {
  for (const node of doc.querySelectorAll(".filing-passage")) {
    node.classList.remove("filing-passage");
  }
  for (const mark of [...doc.querySelectorAll("mark.filing-cite")]) {
    const parent = mark.parentNode;
    if (parent === null) {
      continue;
    }
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, mark);
    }
    parent.removeChild(mark);
    parent.normalize();
  }
}

function locate(
  doc: Document,
  placement: Exclude<FilingPlacement, { kind: "miss" }>,
): { range: Range; anchor: Element } | null {
  const range = doc.createRange();
  if (placement.kind === "span") {
    const start = doc.getElementById(placement.startId);
    const end = doc.getElementById(placement.endId);
    if (start === null || end === null) {
      return null;
    }
    range.setStartAfter(start);
    range.setEndBefore(end);
    return { range, anchor: start };
  }
  const fact = doc.getElementById(placement.elementId);
  if (fact === null) {
    return null;
  }
  range.selectNodeContents(fact);
  return { range, anchor: fact };
}

function passageOf(range: Range): HTMLElement | null {
  const root = range.commonAncestorContainer;
  const el = root.nodeType === Node.ELEMENT_NODE ? (root as Element) : root.parentElement;
  const block = el?.closest("p, li, h1, h2, h3") ?? null;
  return block instanceof HTMLElement ? block : null;
}

function markRange(doc: Document, range: Range) {
  const root = range.commonAncestorContainer;
  const scope = root.nodeType === Node.ELEMENT_NODE ? (root as Element) : root.parentElement;
  if (scope === null) {
    return;
  }
  const walker = doc.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.nodeType === Node.TEXT_NODE && range.intersectsNode(node)) {
      nodes.push(node as Text);
    }
  }
  for (const node of nodes) {
    const start = node === range.startContainer ? range.startOffset : 0;
    const end = node === range.endContainer ? range.endOffset : node.length;
    if (end <= start) {
      continue;
    }
    const slice = doc.createRange();
    slice.setStart(node, start);
    slice.setEnd(node, end);
    const mark = doc.createElement("mark");
    mark.className = "filing-cite";
    slice.surroundContents(mark);
  }
}
