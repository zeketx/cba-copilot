const TOKEN_KEY = "cba.access_token";
const VERIFIER_KEY = "cba.pkce_verifier";
const EMAIL_KEY = "cba.sign_in_email";

export const AUTH_PREVIEW_PARAM = "auth_preview";

export const SIGN_IN_COPY = {
  linkSent:
    "If this email is approved, you'll get a sign-in link shortly. Open it in this same browser within an hour. If you haven't been approved yet, you can request access.",
  wrongBrowser:
    "This link only works in the browser where you asked for it. Enter your email here and we'll send a new link to this device.",
  expired: "That sign-in link expired or was already used. Send a new one.",
  outOfDate: "This sign-in link is out of date. Enter your email to get a new one.",
  requestSent: "Request sent. We'll email you if you're approved.",
  rateLimited: "Please try again in a little while.",
  sendNewLink: "Send a new link here",
} as const;

export type SignInRedirectKind =
  | "none"
  | "signed_in"
  | "wrong_browser"
  | "expired"
  | "out_of_date";

export type AuthPreviewKind = "wrong_browser" | "expired" | "out_of_date";

export type ClassifiedRedirect =
  | { kind: "none" }
  | { kind: "out_of_date" }
  | { kind: "wrong_browser" }
  | { kind: "expired" }
  | { kind: "exchange"; code: string }
  | { kind: AuthPreviewKind };

export class SignInFailed extends Error {}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function authorizationHeader(): { Authorization: string } | null {
  const token = getAccessToken();
  if (token === null) {
    return null;
  }
  return { Authorization: `Bearer ${token}` };
}

export function rememberedSignInEmail(): string {
  return sessionStorage.getItem(EMAIL_KEY) ?? "";
}

export function otpRequestBody(email: string, codeChallenge: string): {
  email: string;
  create_user: false;
  code_challenge: string;
  code_challenge_method: "s256";
} {
  return {
    email,
    create_user: false,
    code_challenge: codeChallenge,
    code_challenge_method: "s256",
  };
}

export function classifySignInRedirect(input: {
  search: string;
  hash: string;
  hasVerifier: boolean;
}): ClassifiedRedirect {
  const query = paramsFrom(input.search, "?");
  const fragment = paramsFrom(input.hash, "#");
  if (fragment.get("access_token")) {
    return { kind: "out_of_date" };
  }
  const code = query.get("code");
  if (code) {
    if (!input.hasVerifier) {
      return { kind: "wrong_browser" };
    }
    return { kind: "exchange", code };
  }
  if (fragment.has("error") || query.has("error") || query.has("error_code")) {
    return { kind: "expired" };
  }
  const preview = query.get(AUTH_PREVIEW_PARAM);
  if (preview === "wrong_browser" || preview === "expired" || preview === "out_of_date") {
    return { kind: preview };
  }
  return { kind: "none" };
}

export function hasAuthCallback(search: string, hash: string): boolean {
  return classifySignInRedirect({ search, hash, hasVerifier: true }).kind !== "none";
}

export function authPathAfterConsume(pathname: string, hash: string): string {
  if (hash === "#sign-in" || hash === "#request-access") {
    return `${pathname}${hash}`;
  }
  return pathname;
}

export function noticeForRedirect(kind: SignInRedirectKind): string | null {
  switch (kind) {
    case "wrong_browser":
      return SIGN_IN_COPY.wrongBrowser;
    case "expired":
      return SIGN_IN_COPY.expired;
    case "out_of_date":
      return SIGN_IN_COPY.outOfDate;
    case "none":
    case "signed_in":
      return null;
    default: {
      const _exhaustive: never = kind;
      return _exhaustive;
    }
  }
}

function goTrueUrl(path: string): string {
  const base = import.meta.env.VITE_SUPABASE_URL;
  if (!base) {
    throw new SignInFailed();
  }
  return `${base.replace(/\/$/, "")}${path}`;
}

function anonKey(): string {
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!key) {
    throw new SignInFailed();
  }
  return key;
}

export async function requestSignInLink(email: string): Promise<"sent" | "rate_limited"> {
  sessionStorage.setItem(EMAIL_KEY, email);
  const verifier = randomVerifier();
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  const codeChallenge = await s256Challenge(verifier);
  const redirectTo = encodeURIComponent(`${window.location.origin}/`);
  let response: Response;
  try {
    response = await fetch(goTrueUrl(`/auth/v1/otp?redirect_to=${redirectTo}`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: anonKey(),
      },
      body: JSON.stringify(otpRequestBody(email, codeChallenge)),
    });
  } catch {
    return "sent";
  }
  if (response.status === 429) {
    return "rate_limited";
  }
  return "sent";
}

export async function consumeSignInRedirect(): Promise<SignInRedirectKind> {
  const classified = classifySignInRedirect({
    search: window.location.search,
    hash: window.location.hash,
    hasVerifier: sessionStorage.getItem(VERIFIER_KEY) !== null,
  });
  if (classified.kind === "none") {
    return "none";
  }
  if (classified.kind === "exchange") {
    const verifier = sessionStorage.getItem(VERIFIER_KEY);
    sessionStorage.removeItem(VERIFIER_KEY);
    let signedIn = false;
    if (verifier) {
      try {
        signedIn = await exchangeCode(classified.code, verifier);
      } catch {
        signedIn = false;
      }
    }
    stripAuthParams();
    return signedIn ? "signed_in" : "expired";
  }
  stripAuthParams();
  return classified.kind;
}

async function exchangeCode(code: string, verifier: string): Promise<boolean> {
  const response = await fetch(goTrueUrl("/auth/v1/token?grant_type=pkce"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: anonKey(),
    },
    body: JSON.stringify({ auth_code: code, code_verifier: verifier }),
  });
  if (!response.ok) {
    return false;
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return false;
  }
  if (
    typeof payload !== "object" ||
    payload === null ||
    typeof (payload as { access_token?: unknown }).access_token !== "string" ||
    (payload as { access_token: string }).access_token === ""
  ) {
    return false;
  }
  setAccessToken((payload as { access_token: string }).access_token);
  return true;
}

function stripAuthParams(): void {
  window.history.replaceState(
    null,
    "",
    authPathAfterConsume(window.location.pathname, window.location.hash),
  );
}

function paramsFrom(raw: string, prefix: "?" | "#"): URLSearchParams {
  const trimmed = raw.startsWith(prefix) ? raw.slice(1) : raw;
  return new URLSearchParams(trimmed);
}

function randomVerifier(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function s256Challenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64Url(new Uint8Array(digest));
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}
