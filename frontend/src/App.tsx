import { useMemo, useState } from "react";
import { CitationChip } from "@/components/chat/CitationChip";
import { PdfPageSheet } from "@/components/chat/PdfPageSheet";
import { Button } from "@/components/ui/button";
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
    <div className="flex h-full min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-rule px-4 py-3">
        <div>
          <p className="text-xs tracking-wide text-muted uppercase">2023 NBA CBA</p>
          <h1 className="font-serif text-2xl">CBA Copilot</h1>
        </div>
        <Button variant="ghost" className="md:hidden" onClick={() => setGlossaryOpen(true)}>
          Definitions
        </Button>
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
            {turns.length === 0 ? (
              <div className="mx-auto max-w-2xl">
                <p className="font-serif text-xl leading-snug">
                  Ask a cap question. Answers cite the 2023 CBA, or they refuse.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {SAMPLE_QUESTIONS.map((sample) => (
                    <Button key={sample} variant="ghost" onClick={() => void ask(sample)}>
                      {sample}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
            {turns.map((turn) => (
              <article key={turn.id} className="mx-auto max-w-2xl space-y-3">
                <p className="text-sm text-muted">{turn.question}</p>
                {turn.response.kind === "refusal" ? (
                  <p className="rounded-lg border border-rule bg-chip px-3 py-2 text-sm text-warn">
                    {turn.response.message}
                  </p>
                ) : (
                  turn.response.claims.map((claim) => (
                    <div key={claim.text} className="space-y-2">
                      <p className="text-sm leading-relaxed">{claim.text}</p>
                      <div className="flex flex-wrap gap-2">
                        {claim.citations.map((citation, index) => (
                          <CitationChip
                            key={citation.passageId}
                            index={index + 1}
                            citation={citation}
                            selected={active?.passageId === citation.passageId}
                            onSelect={setActive}
                          />
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </article>
            ))}
            {error ? <p className="mx-auto max-w-2xl text-sm text-warn">{error}</p> : null}
          </div>
          <form
            className="border-t border-rule px-4 py-3"
            onSubmit={(event) => {
              event.preventDefault();
              void ask(question);
            }}
          >
            <div className="mx-auto flex max-w-2xl gap-2">
              <label className="sr-only" htmlFor="question">
                Question
              </label>
              <input
                id="question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask about the 2023 CBA"
                className="min-w-0 flex-1 rounded-full border border-rule bg-paper px-4 py-2 text-sm outline-none"
              />
              <Button type="submit" disabled={pending || question.trim() === ""}>
                {pending ? "Asking" : "Ask"}
              </Button>
            </div>
          </form>
        </main>
        <PdfPageSheet citation={active} onClose={() => setActive(null)} />
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
