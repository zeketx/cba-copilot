import { useMemo, useState } from "react";
import { Button } from "@/components/beautifui/Button";
import ContextCards, { type ContextChunk } from "@/components/beautifui/ContextCards";
import LoadingState from "@/components/beautifui/LoadingState";
import { StreamText } from "@/components/beautifui/StreamText";
import { SourcePanel } from "@/components/chat/SourcePanel";
import { DefinitionsSidebar } from "@/components/reference/DefinitionsSidebar";
import { loadDefinitions } from "@/lib/definitions";
import {
  SAMPLE_QUESTIONS,
  responseFromWire,
  type ChatTurn,
  type PublicCitation,
  type WireResponse,
} from "@/lib/types";

export function App() {
  const glossary = useMemo(() => loadDefinitions(), []);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<PublicCitation | null>(null);
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) {
      return;
    }
    setPending(true);
    setError(null);
    setQuestion("");
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      if (!response.ok) {
        throw new Error(`The API returned ${response.status}.`);
      }
      const body = (await response.json()) as WireResponse;
      const parsed = responseFromWire(body);
      setTurns((current) => [
        ...current,
        { id: crypto.randomUUID(), question: trimmed, response: parsed },
      ]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "The request failed.";
      setError(message);
      setQuestion(trimmed);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto flex h-full min-h-screen max-w-5xl flex-col bg-page shadow-raised">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <p className="font-mono text-[11px] tracking-wide text-ink-3 uppercase">Fixture mode</p>
          <h1 className="text-lg font-semibold text-ink">CBA Copilot</h1>
        </div>
        <Button
          type="button"
          variant="quiet"
          size="sm"
          className="md:hidden"
          onClick={() => setGlossaryOpen(true)}
        >
          Definitions
        </Button>
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
            {turns.length === 0 ? (
              <div className="mx-auto max-w-2xl rounded-card bg-surface p-4 shadow-card">
                <p className="text-[13px] leading-relaxed text-ink">
                  Fixture mode. Replies use the checked-in demo passages. They are not a live
                  reading of the official PDF, and they are not legal advice.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SAMPLE_QUESTIONS.map((sample) => (
                    <Button
                      key={sample}
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-auto whitespace-normal px-3 py-1.5 text-left"
                      onClick={() => void ask(sample)}
                    >
                      {sample}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
            {turns.map((turn) => (
              <article key={turn.id} className="mx-auto max-w-2xl space-y-3">
                <div className="flex justify-end pl-14">
                  <p className="rounded-xl bg-field px-3 py-1.5 text-[13px] leading-[1.4] text-ink">
                    {turn.question}
                  </p>
                </div>
                {turn.response.kind === "refusal" ? (
                  <div className="rounded-card bg-red-tint px-3 py-2 text-[13px] leading-relaxed text-ink">
                    <StreamText text={turn.response.message} />
                  </div>
                ) : (
                  turn.response.claims.map((claim) => (
                    <div key={claim.text} className="space-y-3">
                      <p className="text-[13px] leading-relaxed text-ink">
                        <StreamText text={claim.text} />
                      </p>
                      <ContextCards
                        className="max-w-none"
                        chunks={claim.citations.map((citation) =>
                          citationChunk(citation, active?.passageId === citation.passageId),
                        )}
                        labels={{
                          header: "Retrieved passages",
                          count: String(claim.citations.length),
                        }}
                        onOpen={(_chunk, index) => {
                          const citation = claim.citations[index];
                          if (citation) {
                            setActive(citation);
                          }
                        }}
                      />
                    </div>
                  ))
                )}
              </article>
            ))}
            {pending ? (
              <div className="mx-auto max-w-2xl">
                <LoadingState label="Reading the fixture" />
              </div>
            ) : null}
            {error ? <p className="mx-auto max-w-2xl text-[13px] text-red">{error}</p> : null}
          </div>
          <form
            className="border-t border-line px-4 py-3"
            onSubmit={(event) => {
              event.preventDefault();
              void ask(question);
            }}
          >
            <div className="mx-auto flex max-w-2xl flex-col gap-2 rounded-control border border-line bg-field p-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.035)]">
              <label className="sr-only" htmlFor="question">
                Question
              </label>
              <input
                id="question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask about the 2023 CBA"
                className="min-h-4.5 bg-transparent text-[13px] leading-[1.4] text-ink outline-none placeholder:text-ink-3"
              />
              <div className="flex items-center justify-end">
                <Button type="submit" variant="primary" size="sm" disabled={pending || question.trim() === ""}>
                  {pending ? "Asking" : "Ask"}
                </Button>
              </div>
            </div>
          </form>
        </main>
        <SourcePanel citation={active} onClose={() => setActive(null)} />
        <DefinitionsSidebar
          status={glossary.status}
          entries={glossary.entries}
          open={glossaryOpen}
          onClose={() => setGlossaryOpen(false)}
        />
      </div>
    </div>
  );
}

function citationChunk(citation: PublicCitation, selected: boolean): ContextChunk {
  const pages =
    citation.pageStart == null
      ? "PDF"
      : citation.pageEnd != null && citation.pageEnd !== citation.pageStart
        ? `pp. ${citation.pageStart}–${citation.pageEnd}`
        : `p. ${citation.pageStart}`;
  const article = citation.articleNumber == null ? "Article" : `Art. ${citation.articleNumber}`;
  const excerpt = citation.excerpt.trim();
  return {
    title: `${article} § ${citation.section}`,
    chars: pages,
    body: excerpt || citation.pageOrSection,
    source: citation.pageOrSection,
    badge: "CBA",
    tone: "bg-accent",
    selected,
  };
}
