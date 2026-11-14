import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { compactCitationLabel } from "@/lib/citation";
import type { PublicCitation, PublicClaim } from "@/lib/types";
import { cn } from "@/lib/utils";

/* ─────────────────────────────────────────────────────────
 * CITED ANSWER
 * Adapted from Beautiful UI's StreamingText: inline source
 * chips in the prose, then an action row with a collapsed
 * "N sources" list. No fake streaming; the reply is final.
 * ───────────────────────────────────────────────────────── */

type CitedAnswerProps = {
  claims: PublicClaim[];
  active: PublicCitation | null;
  onOpen: (citation: PublicCitation) => void;
  markdown?: boolean;
};

/** Unique citations across the whole answer, in first-cited order. */
function answerSources(claims: PublicClaim[]): PublicCitation[] {
  const seen = new Map<string, PublicCitation>();
  for (const claim of claims) {
    for (const citation of claim.citations) {
      if (!seen.has(citation.passageId)) {
        seen.set(citation.passageId, citation);
      }
    }
  }
  return [...seen.values()];
}

function copyText(claims: PublicClaim[]): string {
  const body = claims
    .map((claim) => {
      const labels = claim.citations.map((citation) => `[${compactCitationLabel(citation)}]`);
      return [claim.text, ...labels].join(" ");
    })
    .join("\n\n");
  return body;
}

function pagesLabel(citation: PublicCitation): string {
  if (citation.pageStart === null) {
    return "PDF";
  }
  if (citation.pageEnd !== null && citation.pageEnd !== citation.pageStart) {
    return `pp. ${citation.pageStart}–${citation.pageEnd}`;
  }
  return `p. ${citation.pageStart}`;
}

function SourceChip({
  citation,
  selected,
  onOpen,
}: {
  citation: PublicCitation;
  selected: boolean;
  onOpen: (citation: PublicCitation) => void;
}) {
  const label = compactCitationLabel(citation);
  return (
    <button
      type="button"
      aria-label={`Open source ${label}: ${citation.section}`}
      aria-pressed={selected}
      onClick={() => onOpen(citation)}
      className={cn(
        "mr-1 inline-flex h-[18px] translate-y-[-1px] items-center rounded-[5px] px-[5px] align-middle font-mono text-[10.5px] leading-none whitespace-nowrap shadow-hairline transition-colors duration-150",
        selected
          ? "bg-accent-tint text-accent-ink"
          : "bg-inset text-ink-2 hover:bg-hover hover:text-ink",
      )}
      style={{ animation: "pop-in 250ms cubic-bezier(0.23,1,0.32,1) both" }}
    >
      {label}
    </button>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) {
      return;
    }
    const reset = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(reset);
  }, [copied]);
  return (
    <button
      type="button"
      aria-label={copied ? "Copied" : "Copy answer"}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setCopied(true));
      }}
      className="flex size-6 items-center justify-center rounded-[6px] text-ink-3 transition-colors duration-100 hover:bg-hover-2 hover:text-ink-2"
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {copied ? (
          <path d="M20 6 9 17l-5-5" />
        ) : (
          <g>
            <rect x="9" y="9" width="12" height="12" rx="2.5" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </g>
        )}
      </svg>
    </button>
  );
}

const PROSE =
  "text-[13px] leading-relaxed text-ink [&_a]:text-accent [&_code]:rounded-sm [&_code]:bg-field [&_code]:px-1 [&_code]:font-mono [&_code]:text-[12px] [&_li]:my-0.5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-2 [&_strong]:font-medium [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5";

export function CitedAnswer({ claims, active, onOpen, markdown = false }: CitedAnswerProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sources = answerSources(claims);
  const listId = `sources-${sources[0]?.passageId ?? "none"}-${claims.length}`;

  return (
    <div className="w-full min-w-0">
      <div className="space-y-2 break-words">
        {claims.map((claim, index) => (
          // The last paragraph runs inline so the chips sit at the end of the sentence.
          <div
            key={`${index}-${claim.text}`}
            className={cn(PROSE, "[&>p:nth-last-child(2)]:mb-0 [&>p:nth-last-child(2)]:inline")}
          >
            {markdown ? <Markdown>{claim.text}</Markdown> : <p>{claim.text}</p>}
            <span className="ml-1 inline [overflow-wrap:anywhere]">
              {claim.citations.map((citation) => (
                <SourceChip
                  key={citation.passageId}
                  citation={citation}
                  selected={active?.passageId === citation.passageId}
                  onOpen={onOpen}
                />
              ))}
            </span>
          </div>
        ))}
      </div>

      {sources.length > 0 ? (
        <>
          <div className="mt-2 flex items-center gap-0.5">
            <CopyButton text={copyText(claims)} />
            <button
              type="button"
              aria-expanded={sourcesOpen}
              aria-controls={listId}
              onClick={() => setSourcesOpen((open) => !open)}
              className="ml-1 flex items-center gap-1.5 rounded-[6px] px-1.5 py-0.5 text-left transition-colors duration-150 hover:bg-hover"
            >
              <span
                aria-hidden
                className="flex size-3.5 items-center justify-center rounded-[4px] bg-accent font-mono text-[8px] font-semibold text-white"
              >
                C
              </span>
              <span className="text-[12px] text-ink-2">
                {sources.length} {sources.length === 1 ? "source" : "sources"}
              </span>
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--ink-3)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
                className={cn("transition-transform duration-200", sourcesOpen ? "rotate-180" : "")}
              >
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>
          </div>

          <div
            className={cn(
              "md:grid md:transition-[grid-template-rows,opacity] md:duration-300",
              sourcesOpen
                ? "max-md:fixed max-md:inset-0 max-md:z-30 max-md:flex max-md:flex-col max-md:bg-surface max-md:pt-[env(safe-area-inset-top)] max-md:pb-[env(safe-area-inset-bottom)]"
                : "max-md:hidden",
            )}
            style={{
              gridTemplateRows: sourcesOpen ? "1fr" : "0fr",
              opacity: sourcesOpen ? 1 : 0,
              transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
            }}
          >
            <div className="hidden shrink-0 items-center justify-between border-b border-line px-4 py-3 max-md:flex">
              <h2 className="text-base font-semibold text-ink">Sources</h2>
              <button
                type="button"
                onClick={() => setSourcesOpen(false)}
                className="rounded-control px-2 py-1 text-[13px] text-ink-2 hover:bg-hover hover:text-ink"
              >
                Close
              </button>
            </div>
            <div className="overflow-hidden max-md:min-h-0 max-md:flex-1 max-md:overflow-y-auto max-md:opacity-100">
              <ol
                id={listId}
                hidden={!sourcesOpen}
                className="mt-1.5 flex flex-col rounded-[10px] bg-inset p-1 shadow-hairline max-md:mx-4 max-md:mt-3 max-md:mb-4"
              >
                {sources.map((citation) => {
                  const selected = active?.passageId === citation.passageId;
                  return (
                    <li key={citation.passageId} className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => onOpen(citation)}
                        aria-pressed={selected}
                        className={cn(
                          "flex min-w-0 flex-1 items-center gap-2 rounded-[6px] px-1.5 py-1 text-left text-[12px] transition-colors duration-150",
                          selected ? "bg-accent-tint text-ink" : "text-ink-2 hover:bg-hover hover:text-ink",
                        )}
                      >
                        <span className="shrink-0 font-mono text-[10.5px] text-ink">
                          {compactCitationLabel({ ...citation, section: "", pageStart: null })}
                        </span>
                        <span className="min-w-0 flex-1 truncate">{citation.section}</span>
                        <span className="shrink-0 font-mono text-[10.5px] text-ink-3">
                          {pagesLabel(citation)}
                        </span>
                      </button>
                      <a
                        href={citation.sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Open the official PDF at ${compactCitationLabel(citation)}`}
                        className="shrink-0 rounded-[6px] px-1.5 py-1 font-mono text-[10.5px] text-ink-3 transition-colors duration-150 hover:bg-hover hover:text-ink"
                      >
                        PDF ↗
                      </a>
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
