import { getAccessToken } from "@/lib/session";

const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  readonly kind: "network" | "http";
  readonly status: number | null;

  constructor(kind: "network" | "http", message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

type ApiRequestInit = Omit<RequestInit, "signal"> & {
  timeoutMs?: number;
  auth?: boolean;
};

export async function apiRequest(path: string, init: ApiRequestInit = {}): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, auth = true, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  if (auth) {
    const token = getAccessToken();
    if (token !== null && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }
  const base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(`${base}${path}`, { ...rest, headers, signal: controller.signal });
  } catch {
    throw new ApiError("network", "The request did not reach the server.");
  } finally {
    window.clearTimeout(timer);
  }
}
