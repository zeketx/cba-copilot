import { ApiError, apiRequest } from "@/lib/http";
import { getAccessToken } from "@/lib/session";
import {
  messageFromWire,
  responseFromWire,
  threadFromWire,
  type ChatMessage,
  type PublicResponse,
  type StreamChatMessage,
  type ThreadSummary,
  type WireChatMessage,
  type WireResponse,
  type WireThread,
} from "@/lib/types";

export async function listThreads(): Promise<ThreadSummary[]> {
  const response = await apiRequest("/api/threads");
  const body = await readJson<WireThread[]>(response);
  return body.map(threadFromWire);
}

export async function createThread(): Promise<ThreadSummary> {
  const response = await apiRequest("/api/threads", { method: "POST" });
  return threadFromWire(await readJson<WireThread>(response));
}

export async function loadMessages(threadId: string): Promise<ChatMessage[]> {
  const response = await apiRequest(`/api/threads/${threadId}/messages`);
  const body = await readJson<WireChatMessage[]>(response);
  return body.map(messageFromWire);
}

export async function streamAsk(
  threadId: string,
  messages: StreamChatMessage[],
): Promise<{ threadId: string; turnId: string; response: PublicResponse }> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = getAccessToken();
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetch(`${base}/api/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ threadId, messages }),
    });
  } catch {
    throw new ApiError("network", "The request did not reach the server.");
  }
  if (!response.ok) {
    throw await httpError(response);
  }
  const collected: {
    value: { threadId: string; turnId: string; response: PublicResponse } | null;
  } = { value: null };
  await readSse(response, (event, data) => {
    if (event === "delta") {
      return;
    }
    if (event === "done" && isRecord(data)) {
      if (
        typeof data.thread_id !== "string" ||
        typeof data.turn_id !== "string" ||
        !isRecord(data.response)
      ) {
        return;
      }
      collected.value = {
        threadId: data.thread_id,
        turnId: data.turn_id,
        response: responseFromWire(data.response as WireResponse),
      };
    }
  });
  if (collected.value === null) {
    throw new ApiError("http", "The API returned no stream.", response.status);
  }
  return collected.value;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await httpError(response);
  }
  return (await response.json()) as T;
}

async function httpError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { detail?: { error?: string } };
    if (typeof body.detail?.error === "string") {
      return new ApiError("http", body.detail.error, response.status);
    }
  } catch {
    return new ApiError("http", `The API returned ${response.status}.`, response.status);
  }
  return new ApiError("http", `The API returned ${response.status}.`, response.status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function readSse(
  response: Response,
  onEvent: (event: string, data: unknown) => void,
): Promise<void> {
  const reader = response.body?.getReader();
  if (reader === undefined) {
    throw new ApiError("http", "The API returned no stream.", response.status);
  }
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatchSse(buffer.slice(0, boundary), onEvent);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim() !== "") {
    dispatchSse(buffer, onEvent);
  }
}

function dispatchSse(block: string, onEvent: (event: string, data: unknown) => void): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (dataLines.length === 0) {
    return;
  }
  onEvent(event, JSON.parse(dataLines.join("\n")) as unknown);
}
