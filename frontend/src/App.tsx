import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/beautifui/Button";
import ContextCards, { type ContextChunk } from "@/components/beautifui/ContextCards";
import LoadingState from "@/components/beautifui/LoadingState";
import SidebarNav from "@/components/beautifui/SidebarNav";
import { StreamText } from "@/components/beautifui/StreamText";
import { SourcePanel } from "@/components/chat/SourcePanel";
import { DefinitionsSidebar } from "@/components/reference/DefinitionsSidebar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { createThread, deleteThread, listThreads, loadMessages, renameThread, streamAsk } from "@/lib/api";
import { loadDefinitions } from "@/lib/definitions";
import { ApiError, apiRequest } from "@/lib/http";
import {
  clearAccessToken,
  completeSignIn,
  getAccessToken,
  requestSignInCode,
} from "@/lib/session";
import {
  SAMPLE_QUESTIONS,
  type ChatMessage,
  type PublicClaim,
  type PublicCitation,
  type PublicResponse,
  type ThreadSummary,
} from "@/lib/types";

const ACTIVE_THREAD_KEY = "cba.active_thread_id";

function replyText(response: PublicResponse): string {
  switch (response.kind) {
    case "refusal":
    case "clarification":
      return response.message;
    case "answer":
      return response.claims.map((claim) => claim.text).join("\n\n");
    default: {
      const _exhaustive: never = response;
      return _exhaustive;
    }
  }
}

export function App() {
  const glossary = useMemo(() => loadDefinitions(), []);
  const [question, setQuestion] = useState("");
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [liveDelta, setLiveDelta] = useState<string | null>(null);
  const settleThread = useRef<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<PublicCitation | null>(null);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [sessionToken, setSessionToken] = useState<string | null>(() => getAccessToken());
  const [requestEmail, setRequestEmail] = useState("");
  const [requestState, setRequestState] = useState<
    "idle" | "sending" | "sent" | "leaving" | "failed"
  >("idle");
  const [signInEmail, setSignInEmail] = useState("");
  const [signInCode, setSignInCode] = useState("");
  const [signInNotice, setSignInNotice] = useState<string | null>(null);
  const [notAllowed, setNotAllowed] = useState(false);
  const [gateView, setGateView] = useState<"request" | "login">("request");

  useEffect(() => {
    if (requestState !== "sent") {
      return;
    }
    const fade = window.setTimeout(() => setRequestState("leaving"), 1400);
    return () => window.clearTimeout(fade);
  }, [requestState]);

  useEffect(() => {
    if (requestState !== "leaving") {
      return;
    }
    const clear = window.setTimeout(() => setRequestState("idle"), 1200);
    return () => window.clearTimeout(clear);
  }, [requestState]);

  useEffect(() => {
    if (sessionToken === null) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const listed = await listThreads();
        if (cancelled) {
          return;
        }
        setThreads(listed);
        const hint = sessionStorage.getItem(ACTIVE_THREAD_KEY);
        const chosen = listed.find((thread) => thread.id === hint)?.id ?? null;
        setActiveThreadId(chosen);
        if (chosen === null) {
          setMessages([]);
          return;
        }
        const loaded = await loadMessages(chosen);
        if (!cancelled) {
          setMessages(loaded);
        }
      } catch (caught) {
        if (cancelled) {
          return;
        }
        handleRequestError(caught);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  async function submitAccessRequest(email: string) {
    const trimmed = email.trim();
    if (!trimmed || requestState === "sending") {
      return;
    }
    setRequestState("sending");
    let response: Response;
    try {
      response = await apiRequest("/api/access-requests", {
        method: "POST",
        auth: false,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
    } catch (caught) {
      if (caught instanceof ApiError && caught.kind === "network") {
        setRequestState("failed");
        return;
      }
      throw caught;
    }
    if (!response.ok) {
      setRequestState("failed");
      return;
    }
    setRequestState("sent");
  }

  async function sendCode() {
    const email = signInEmail.trim();
    if (!email) {
      return;
    }
    setSignInNotice(null);
    try {
      await requestSignInCode(email);
      setSignInNotice("Enter the six-digit code from your email.");
    } catch {
      setSignInNotice("This address cannot sign in.");
    }
  }

  async function finishSignIn() {
    const email = signInEmail.trim();
    const code = signInCode.trim();
    if (!email || !code) {
      return;
    }
    setSignInNotice(null);
    try {
      await completeSignIn(email, code);
      setSessionToken(getAccessToken());
      setNotAllowed(false);
      setSignInCode("");
    } catch {
      setSignInNotice("This address cannot sign in.");
    }
  }

  function handleRequestError(caught: unknown): boolean {
    if (caught instanceof ApiError && caught.status === 401) {
      clearAccessToken();
      setSessionToken(getAccessToken());
      setNotAllowed(false);
      setGateView("login");
      return true;
    }
    if (caught instanceof ApiError && caught.status === 403 && caught.message === "not_allowed") {
      setNotAllowed(true);
      return true;
    }
    return false;
  }

  async function openThread(threadId: string) {
    sessionStorage.setItem(ACTIVE_THREAD_KEY, threadId);
    setActiveThreadId(threadId);
    setError(null);
    setLiveDelta(null);
    try {
      setMessages(await loadMessages(threadId));
    } catch (caught) {
      if (handleRequestError(caught)) {
        return;
      }
      setMessages([]);
      const message =
        caught instanceof ApiError && caught.kind === "network"
          ? "The request did not reach the server."
          : caught instanceof Error
            ? caught.message
            : "The request failed.";
      setError(message);
    }
  }

  function signOut() {
    clearAccessToken();
    sessionStorage.removeItem(ACTIVE_THREAD_KEY);
    setSessionToken(null);
    setThreads([]);
    setActiveThreadId(null);
    setMessages([]);
    setLiveDelta(null);
    setError(null);
    setGlossaryOpen(false);
    setNotAllowed(false);
  }

  function requestFailedMessage(caught: unknown): string {
    if (caught instanceof ApiError && caught.kind === "network") {
      return "The request did not reach the server.";
    }
    if (caught instanceof Error) {
      return caught.message;
    }
    return "The request failed.";
  }

  async function renameActiveThread(id: string, title: string) {
    try {
      const updated = await renameThread(id, title);
      setThreads((current) =>
        [...current.map((item) => (item.id === updated.id ? updated : item))].sort(
          (left, right) => right.updatedAt.localeCompare(left.updatedAt),
        ),
      );
      setError(null);
    } catch (caught) {
      if (!handleRequestError(caught)) {
        setError(requestFailedMessage(caught));
      }
    }
  }

  async function deleteActiveThread(id: string) {
    try {
      await deleteThread(id);
      setThreads((current) => current.filter((item) => item.id !== id));
      if (activeThreadId === id) {
        sessionStorage.removeItem(ACTIVE_THREAD_KEY);
        setActiveThreadId(null);
        setMessages([]);
        setLiveDelta(null);
      }
      setError(null);
    } catch (caught) {
      if (!handleRequestError(caught)) {
        setError(requestFailedMessage(caught));
      }
    }
  }

  async function startThread() {
    try {
      const thread = await createThread();
      sessionStorage.setItem(ACTIVE_THREAD_KEY, thread.id);
      setThreads((current) => [thread, ...current.filter((item) => item.id !== thread.id)]);
      setActiveThreadId(thread.id);
      setMessages([]);
      setLiveDelta(null);
      setError(null);
    } catch (caught) {
      if (!handleRequestError(caught)) {
        const message =
          caught instanceof ApiError && caught.kind === "network"
            ? "The request did not reach the server."
            : caught instanceof Error
              ? caught.message
              : "The request failed.";
        setError(message);
      }
    }
  }

  async function settleLive() {
    const threadId = settleThread.current;
    if (threadId === null) {
      return;
    }
    settleThread.current = null;
    try {
      const [loaded, listed] = await Promise.all([loadMessages(threadId), listThreads()]);
      setMessages(loaded);
      setThreads(listed);
      setLiveDelta(null);
    } catch (caught) {
      if (!handleRequestError(caught)) {
        setError(caught instanceof Error ? caught.message : "The request failed.");
      }
    } finally {
      setPending(false);
    }
  }

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) {
      return;
    }
    if (getAccessToken() === null) {
      clearAccessToken();
      setSessionToken(null);
      return;
    }
    setPending(true);
    setError(null);
    setQuestion("");
    setLiveDelta(null);
    const turnId = crypto.randomUUID();
    let threadId = activeThreadId;
    let appended = false;
    try {
      if (threadId === null) {
        const thread = await createThread();
        threadId = thread.id;
        sessionStorage.setItem(ACTIVE_THREAD_KEY, thread.id);
        setThreads((current) => [thread, ...current]);
        setActiveThreadId(thread.id);
      }
      setMessages((current) => [
        ...current,
        {
          id: turnId,
          role: "user",
          position: current.length,
          text: trimmed,
        },
      ]);
      appended = true;
      const finished = await streamAsk(threadId, [
        { id: turnId, role: "user", content: trimmed },
      ]);
      settleThread.current = threadId;
      setLiveDelta(replyText(finished.response));
    } catch (caught) {
      settleThread.current = null;
      if (appended) {
        setMessages((current) => current.filter((message) => message.id !== turnId));
      }
      setLiveDelta(null);
      setPending(false);
      if (handleRequestError(caught)) {
        return;
      }
      const message =
        caught instanceof ApiError && caught.kind === "network"
          ? "The request did not reach the server."
          : caught instanceof Error
            ? caught.message
            : "The request failed.";
      setError(message);
      setQuestion(trimmed);
    }
  }

  const gatePanel =
    gateView === "request" ? (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submitAccessRequest(requestEmail);
        }}
      >
        <DialogHeader>
          <DialogTitle>Request access</DialogTitle>
          <DialogDescription>Leave an email. This does not create an account.</DialogDescription>
        </DialogHeader>
        <label className="sr-only" htmlFor="access-email">
          Email
        </label>
        <Input
          id="access-email"
          type="email"
          autoComplete="email"
          value={requestEmail}
          onChange={(event) => setRequestEmail(event.target.value)}
          placeholder="you@example.com"
          className="mt-4"
        />
        <Button
          type="submit"
          variant="primary"
          size="md"
          className="mt-4 w-full"
          disabled={requestState === "sending"}
        >
          Request access
        </Button>
        <div className="mt-3 h-5 overflow-hidden" aria-live="polite">
          {requestState === "sent" || requestState === "leaving" ? (
            <p
              className="flex items-center gap-1.5 text-[13px] text-green transition-opacity duration-[1200ms]"
              style={{ opacity: requestState === "leaving" ? 0 : 1 }}
            >
              <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
                <path
                  d="M3.5 8.5 6.5 11.5 12.5 4.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Request sent
            </p>
          ) : null}
          {requestState === "failed" ? (
            <p className="text-[13px] text-ink-3">That email could not be saved.</p>
          ) : null}
        </div>
        <p className="mt-4 text-[13px] leading-relaxed text-ink-2">
          If you already have a login,{" "}
          <Button
            type="button"
            variant="quiet"
            size="sm"
            className="h-auto px-1 text-accent"
            onClick={() => setGateView("login")}
          >
            Go to login
          </Button>
        </p>
      </form>
    ) : (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void finishSignIn();
        }}
      >
        <DialogHeader>
          <DialogTitle>Sign in</DialogTitle>
          <DialogDescription>
            If this is your first time, enter the email we invited and send a code.
          </DialogDescription>
        </DialogHeader>
        <label className="sr-only" htmlFor="sign-in-email">
          Sign-in email
        </label>
        <Input
          id="sign-in-email"
          type="email"
          autoComplete="email"
          value={signInEmail}
          onChange={(event) => setSignInEmail(event.target.value)}
          placeholder="invited@example.com"
          className="mt-4"
        />
        <label className="sr-only" htmlFor="sign-in-code">
          Six-digit code
        </label>
        <Input
          id="sign-in-code"
          inputMode="numeric"
          autoComplete="one-time-code"
          value={signInCode}
          onChange={(event) => setSignInCode(event.target.value)}
          placeholder="123456"
          className="mt-2"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={() => void sendCode()}>
            Send code
          </Button>
          <Button type="submit" variant="primary" size="sm">
            Sign in
          </Button>
        </div>
        {signInNotice ? <p className="mt-3 text-[13px] text-ink-3">{signInNotice}</p> : null}
        <p className="mt-4 text-[13px] leading-relaxed text-ink-2">
          <Button
            type="button"
            variant="quiet"
            size="sm"
            className="h-auto px-1 text-accent"
            onClick={() => setGateView("request")}
          >
            Request access
          </Button>
        </p>
      </form>
    );

  return (
    <>
      <Dialog open={sessionToken === null} onOpenChange={() => {}}>
        <DialogContent
          showCloseButton={false}
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
        >
          <div
            key={gateView}
            style={{ animation: "fade-up 220ms cubic-bezier(0.16, 1, 0.3, 1) both" }}
          >
            {gatePanel}
          </div>
        </DialogContent>
      </Dialog>
      {sessionToken === null ? (
        <div className="min-h-screen" />
      ) : (
    <div className="mx-auto flex h-full min-h-screen max-w-5xl flex-col bg-page shadow-raised">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <p className="font-mono text-[11px] tracking-wide text-ink-3 uppercase">Fixture mode</p>
          <h1 className="text-lg font-semibold text-ink">CBA Copilot</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="quiet" size="sm" className="md:hidden" onClick={() => void startThread()}>
            New chat
          </Button>
          <Button
            type="button"
            variant="quiet"
            size="sm"
            className="md:hidden"
            onClick={() => setGlossaryOpen(true)}
          >
            Definitions
          </Button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <SidebarNav
          fill
          className="hidden border-r border-line md:flex"
          recents={threads.map((thread) => ({ id: thread.id, label: thread.title }))}
          activeId={activeThreadId}
          activeNav={glossaryOpen ? "definitions" : "chats"}
          userEmail={signInEmail}
          onNewChat={() => void startThread()}
          onPick={(id) => void openThread(id)}
          onNavigate={(key) => setGlossaryOpen(key === "definitions")}
          onRename={(id, title) => void renameActiveThread(id, title)}
          onDelete={(id) => void deleteActiveThread(id)}
          onSignOut={signOut}
        />
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
            {notAllowed ? (
              <p className="mx-auto max-w-2xl text-[13px] text-red">
                This email is signed in and is not on the allow-list.
              </p>
            ) : null}
                {messages.length === 0 ? (
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
                {messages.map((message, index) => {
                  if (message.role !== "user") {
                    return null;
                  }
                  const next = messages[index + 1];
                  const assistant = next?.role === "assistant" ? next : null;
                      const showLive =
                        liveDelta !== null && assistant === null && index === messages.length - 1;
                  return (
                    <article key={message.id} className="mx-auto max-w-2xl space-y-3">
                      <div className="flex justify-end pl-14">
                        <p className="rounded-xl bg-field px-3 py-1.5 text-[13px] leading-[1.4] text-ink">
                          {message.text}
                        </p>
                      </div>
                      {assistant !== null ? (
                        <StaticReply
                          response={assistant.response}
                          active={active}
                          onOpen={setActive}
                        />
                      ) : null}
                      {showLive ? (
                        <p className="text-[13px] leading-relaxed text-ink">
                          <StreamText text={liveDelta} onDone={() => void settleLive()} />
                        </p>
                      ) : null}
                    </article>
                  );
                })}
                {pending && liveDelta === null ? (
                  <div className="mx-auto max-w-2xl">
                    <LoadingState variant="Orbit" label="Reading the fixture" />
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
      )}
    </>
  );
}

function ClaimCards({
  claims,
  active,
  onOpen,
}: {
  claims: PublicClaim[];
  active: PublicCitation | null;
  onOpen: (citation: PublicCitation) => void;
}) {
  return (
    <>
      {claims.map((claim) => (
        <div key={claim.text} className="space-y-3">
          <p className="text-[13px] leading-relaxed text-ink">{claim.text}</p>
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
                onOpen(citation);
              }
            }}
          />
        </div>
      ))}
    </>
  );
}

function StaticReply({
  response,
  active,
  onOpen,
}: {
  response: PublicResponse;
  active: PublicCitation | null;
  onOpen: (citation: PublicCitation) => void;
}) {
  switch (response.kind) {
    case "refusal":
      return (
        <div className="rounded-card bg-red-tint px-3 py-2 text-[13px] leading-relaxed text-ink">
          {response.message}
        </div>
      );
    case "clarification":
      return (
        <>
          <div className="rounded-card bg-surface px-3 py-2 text-[13px] leading-relaxed text-ink">
            {response.message}
          </div>
          <ClaimCards claims={response.claims} active={active} onOpen={onOpen} />
        </>
      );
    case "answer":
      return <ClaimCards claims={response.claims} active={active} onOpen={onOpen} />;
    default: {
      const _exhaustive: never = response;
      return _exhaustive;
    }
  }
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
