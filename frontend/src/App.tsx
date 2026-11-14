import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import { Button } from "@/components/beautifui/Button";
import ContextCards, { type ContextChunk } from "@/components/beautifui/ContextCards";
import SidebarNav from "@/components/beautifui/SidebarNav";
import { StreamText } from "@/components/beautifui/StreamText";
import ThinkingState from "@/components/beautifui/ThinkingState";
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
import {
  createThread,
  deleteThread,
  fetchHealth,
  fetchMe,
  listThreads,
  loadMessages,
  renameThread,
  streamAsk,
} from "@/lib/api";
import { loadDefinitions } from "@/lib/definitions";
import { ApiError, apiRequest } from "@/lib/http";
import { chatRequestError, isAbortError, type ChatRequestError } from "@/lib/request-error";
import {
  clearAccessToken,
  consumeSignInRedirect,
  getAccessToken,
  requestSignInLink,
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

type AskTurn =
  | { phase: "idle" }
  | { phase: "thinking"; threadId: string; turnId: string; question: string }
  | { phase: "streaming"; threadId: string; turnId: string; question: string; text: string }
  | { phase: "revealing"; threadId: string; turnId: string; text: string };

type VisibleError = ChatRequestError & { retryText: string | null };

type SignOutReason = "user" | "session_ended";

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
  const [askTurn, setAskTurn] = useState<AskTurn>({ phase: "idle" });
  const askGeneration = useRef(0);
  const abortAsk = useRef<AbortController | null>(null);
  const settleThread = useRef<string | null>(null);
  const [error, setError] = useState<VisibleError | null>(null);
  const [active, setActive] = useState<PublicCitation | null>(null);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [signInRedirect] = useState(() => consumeSignInRedirect());
  const [sessionToken, setSessionToken] = useState<string | null>(() => getAccessToken());
  const [sessionEmail, setSessionEmail] = useState<string | null>(null);
  const [signOutReason, setSignOutReason] = useState<SignOutReason | null>(null);
  const [requestEmail, setRequestEmail] = useState("");
  const [requestState, setRequestState] = useState<
    "idle" | "sending" | "sent" | "leaving" | "failed"
  >("idle");
  const [signInEmail, setSignInEmail] = useState("");
  const [signInNotice, setSignInNotice] = useState<string | null>(() =>
    signInRedirect === "failed" ? "That sign-in link expired or was already used. Send a new one." : null,
  );
  const [notAllowed, setNotAllowed] = useState(false);
  const [gateView, setGateView] = useState<"request" | "login">(() =>
    signInRedirect === "failed" ? "login" : "request",
  );
  const [fixtureMode, setFixtureMode] = useState<boolean | null>(null);

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
    let cancelled = false;
    void fetchHealth()
      .then((mode) => {
        if (!cancelled) {
          setFixtureMode(mode !== "live");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFixtureMode(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (sessionToken === null) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [me, listed] = await Promise.all([fetchMe(), listThreads()]);
        if (cancelled) {
          return;
        }
        setSessionEmail(me.email);
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

  async function sendLink() {
    const email = signInEmail.trim();
    if (!email) {
      return;
    }
    setSignOutReason(null);
    setSignInNotice(null);
    try {
      await requestSignInLink(email);
      setSignInNotice("Check your email and click the sign-in link.");
    } catch {
      setSignInNotice("This address cannot sign in.");
    }
  }

  function abandonAsk() {
    askGeneration.current += 1;
    abortAsk.current?.abort();
    abortAsk.current = null;
    settleThread.current = null;
    setAskTurn({ phase: "idle" });
  }

  function handleRequestError(caught: unknown, retryText: string | null = null): boolean {
    if (isAbortError(caught)) {
      return true;
    }
    const mapped = chatRequestError(caught);
    if (mapped.signOut) {
      signOut("session_ended");
      return true;
    }
    if (
      caught instanceof ApiError &&
      caught.status === 403 &&
      (caught.code === "not_allowed" || caught.message === "not_allowed")
    ) {
      setNotAllowed(true);
      return true;
    }
    if (mapped.refreshThreads) {
      sessionStorage.removeItem(ACTIVE_THREAD_KEY);
      setActiveThreadId(null);
      setMessages([]);
      void listThreads().then(setThreads, () => undefined);
    }
    setError({ ...mapped, retryText: mapped.retry ? retryText : null });
    return false;
  }

  async function openThread(threadId: string) {
    abandonAsk();
    sessionStorage.setItem(ACTIVE_THREAD_KEY, threadId);
    setActiveThreadId(threadId);
    setError(null);
    try {
      setMessages(await loadMessages(threadId));
    } catch (caught) {
      if (handleRequestError(caught)) {
        return;
      }
      setMessages([]);
    }
  }

  function signOut(reason: SignOutReason) {
    abandonAsk();
    clearAccessToken();
    sessionStorage.removeItem(ACTIVE_THREAD_KEY);
    setSessionToken(null);
    setSessionEmail(null);
    setSignOutReason(reason);
    setThreads([]);
    setActiveThreadId(null);
    setMessages([]);
    setError(null);
    setGlossaryOpen(false);
    setNotAllowed(false);
    if (reason === "session_ended") {
      setGateView("login");
    }
  }

  async function renameChat(id: string, title: string) {
    try {
      const updated = await renameThread(id, title);
      setThreads((current) =>
        [...current.map((item) => (item.id === updated.id ? updated : item))].sort(
          (left, right) => right.updatedAt.localeCompare(left.updatedAt),
        ),
      );
      setError(null);
    } catch (caught) {
      handleRequestError(caught);
    }
  }

  async function deleteChat(id: string) {
    try {
      await deleteThread(id);
      setThreads((current) => current.filter((item) => item.id !== id));
      if (activeThreadId === id) {
        sessionStorage.removeItem(ACTIVE_THREAD_KEY);
        abandonAsk();
        setActiveThreadId(null);
        setMessages([]);
      }
      setError(null);
    } catch (caught) {
      handleRequestError(caught);
    }
  }

  async function startThread() {
    abandonAsk();
    setError(null);
    setMessages([]);
    try {
      const thread = await createThread();
      sessionStorage.setItem(ACTIVE_THREAD_KEY, thread.id);
      setThreads((current) => [thread, ...current.filter((item) => item.id !== thread.id)]);
      setActiveThreadId(thread.id);
      setMessages([]);
    } catch (caught) {
      handleRequestError(caught);
    }
  }

  async function settleLive() {
    const generation = askGeneration.current;
    const threadId = settleThread.current;
    if (threadId === null) {
      return;
    }
    settleThread.current = null;
    try {
      const [loaded, listed] = await Promise.all([loadMessages(threadId), listThreads()]);
      if (generation !== askGeneration.current) {
        return;
      }
      setMessages(loaded);
      setThreads(listed);
      setAskTurn({ phase: "idle" });
    } catch (caught) {
      if (generation !== askGeneration.current) {
        return;
      }
      setAskTurn({ phase: "idle" });
      handleRequestError(caught);
    }
  }

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || askTurn.phase !== "idle") {
      return;
    }
    if (getAccessToken() === null) {
      clearAccessToken();
      setSessionToken(null);
      return;
    }
    const generation = ++askGeneration.current;
    const controller = new AbortController();
    abortAsk.current = controller;
    setError(null);
    setQuestion("");
    const turnId = crypto.randomUUID();
    let threadId = activeThreadId;
    let appended = false;
    let streamed = "";
    try {
      if (threadId === null) {
        const thread = await createThread();
        if (generation !== askGeneration.current) {
          return;
        }
        threadId = thread.id;
        sessionStorage.setItem(ACTIVE_THREAD_KEY, thread.id);
        setThreads((current) => [thread, ...current]);
        setActiveThreadId(thread.id);
      }
      if (threadId === null) {
        return;
      }
      const boundThreadId = threadId;
      setAskTurn({ phase: "thinking", threadId: boundThreadId, turnId, question: trimmed });
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
      const finished = await streamAsk(
        boundThreadId,
        [{ id: turnId, role: "user", content: trimmed }],
        {
          signal: controller.signal,
          onDelta: (chunk) => {
            if (generation !== askGeneration.current) {
              return;
            }
            streamed += chunk;
            setAskTurn({
              phase: "streaming",
              threadId: boundThreadId,
              turnId,
              question: trimmed,
              text: streamed,
            });
          },
        },
      );
      if (generation !== askGeneration.current) {
        return;
      }
      abortAsk.current = null;
      settleThread.current = boundThreadId;
      if (streamed !== "") {
        await settleLive();
        return;
      }
      setAskTurn({
        phase: "revealing",
        threadId: boundThreadId,
        turnId,
        text: replyText(finished.response),
      });
    } catch (caught) {
      if (generation !== askGeneration.current || isAbortError(caught)) {
        return;
      }
      abortAsk.current = null;
      settleThread.current = null;
      if (appended) {
        setMessages((current) => current.filter((message) => message.id !== turnId));
      }
      setAskTurn({ phase: "idle" });
      if (handleRequestError(caught, trimmed)) {
        return;
      }
      setQuestion(trimmed);
    }
  }

  const sessionEndedNotice =
    signOutReason === "session_ended" ? (
      <p className="mt-3 text-[13px] text-ink-3">Your session ended. Sign in again.</p>
    ) : null;

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
        {sessionEndedNotice}
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
          void sendLink();
        }}
      >
        <DialogHeader>
          <DialogTitle>Sign in</DialogTitle>
          <DialogDescription>
            Enter your email and we'll send you a sign-in link. Only approved emails can use the copilot.
          </DialogDescription>
        </DialogHeader>
        {sessionEndedNotice}
        <label className="sr-only" htmlFor="sign-in-email">
          Sign-in email
        </label>
        <Input
          id="sign-in-email"
          type="email"
          autoComplete="email"
          value={signInEmail}
          onChange={(event) => {
            setSignOutReason(null);
            setSignInEmail(event.target.value);
          }}
          placeholder="you@example.com"
          className="mt-4"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="submit" variant="primary" size="sm">
            Send sign-in link
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
          {fixtureMode ? (
            <p className="font-mono text-[11px] tracking-wide text-ink-3 uppercase">Fixture mode</p>
          ) : null}
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
          userEmail={sessionEmail ?? undefined}
          onNewChat={() => void startThread()}
          onPick={(id) => void openThread(id)}
          onNavigate={(key) => setGlossaryOpen(key === "definitions")}
          onRename={(id, title) => void renameChat(id, title)}
          onDelete={(id) => void deleteChat(id)}
          onSignOut={() => signOut("user")}
        />
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex gap-2 overflow-x-auto border-b border-line px-3 py-2 md:hidden">
            {threads.map((thread) => (
              <button
                key={thread.id}
                type="button"
                onClick={() => void openThread(thread.id)}
                className={`shrink-0 rounded-lg px-2 py-1 text-[12px] ${
                  thread.id === activeThreadId ? "bg-field text-ink" : "text-ink-2"
                }`}
              >
                {thread.title.trim() === "" ? "New chat" : thread.title}
              </button>
            ))}
          </div>
          <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
            {notAllowed ? (
              <p className="mx-auto max-w-2xl text-[13px] text-red">
                This email is signed in and is not on the allow-list.
              </p>
            ) : null}
                {messages.length === 0 && askTurn.phase === "idle" ? (
                  <div className="mx-auto max-w-2xl px-1 py-10">
                    <p className="text-[15px] font-medium text-ink">Ask about the 2023 CBA</p>
                    {fixtureMode === false ? (
                      <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
                        Answers cite the 2023 collective bargaining agreement. They are not legal
                        advice.
                      </p>
                    ) : fixtureMode ? (
                      <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
                        Fixture mode. Replies use the checked-in demo passages. They are not a live
                        reading of the official PDF, and they are not legal advice.
                      </p>
                    ) : null}
                    <div className="mt-4 flex flex-wrap gap-2">
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
                      const showTurn =
                        askTurn.phase !== "idle" &&
                        assistant === null &&
                        index === messages.length - 1;
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
                      {showTurn && askTurn.phase === "thinking" ? (
                        <ThinkingState
                          variant="Steps"
                          active="Reading the CBA"
                          done="Read the CBA"
                          rows={[
                            { primary: "Reading the question" },
                            {
                              primary: fixtureMode
                                ? "Retrieving fixture passages"
                                : "Retrieving passages",
                            },
                            { primary: "Drafting a grounded answer" },
                          ]}
                        />
                      ) : null}
                      {showTurn && askTurn.phase === "streaming" ? (
                        <p className="text-[13px] leading-relaxed text-ink">
                          {askTurn.text}
                          <span aria-hidden className="stream-caret is-streaming" />
                        </p>
                      ) : null}
                      {showTurn && askTurn.phase === "revealing" ? (
                        <p className="text-[13px] leading-relaxed text-ink">
                          <StreamText text={askTurn.text} onDone={() => void settleLive()} />
                        </p>
                      ) : null}
                    </article>
                  );
                })}
                {error ? (
                  <div
                    role="alert"
                    className="mx-auto flex max-w-2xl flex-col gap-2 rounded-card border border-line bg-surface px-3 py-3 shadow-card"
                  >
                    <p className="text-[13px] leading-relaxed text-ink">{error.copy}</p>
                    {error.retry && error.retryText ? (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="self-start"
                        onClick={() => void ask(error.retryText ?? "")}
                      >
                        Try again
                      </Button>
                    ) : null}
                  </div>
                ) : null}
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
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={askTurn.phase !== "idle" || question.trim() === ""}
                  >
                    {askTurn.phase !== "idle" ? "Asking" : "Ask"}
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

function AnswerProse({ text }: { text: string }) {
  return (
    <div className="text-[13px] leading-relaxed text-ink [&_a]:text-accent [&_code]:rounded-sm [&_code]:bg-field [&_code]:px-1 [&_code]:font-mono [&_code]:text-[12px] [&_li]:my-0.5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-2 [&_p:last-child]:mb-0 [&_strong]:font-medium [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5">
      <Markdown>{text}</Markdown>
    </div>
  );
}

function ClaimCards({
  claims,
  active,
  onOpen,
  markdown = false,
}: {
  claims: PublicClaim[];
  active: PublicCitation | null;
  onOpen: (citation: PublicCitation) => void;
  markdown?: boolean;
}) {
  return (
    <>
      {claims.map((claim) => (
        <div key={claim.text} className="space-y-3">
          {markdown ? (
            <AnswerProse text={claim.text} />
          ) : (
            <p className="text-[13px] leading-relaxed text-ink">{claim.text}</p>
          )}
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
      return <ClaimCards claims={response.claims} active={active} onOpen={onOpen} markdown />;
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
