const TOKEN_KEY = "cba.access_token";

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

export async function requestSignInLink(email: string): Promise<void> {
  const redirectTo = encodeURIComponent(`${window.location.origin}/`);
  const response = await fetch(goTrueUrl(`/auth/v1/otp?redirect_to=${redirectTo}`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: anonKey(),
    },
    body: JSON.stringify({ email, create_user: true }),
  });
  if (!response.ok) {
    throw new SignInFailed();
  }
}

export type SignInRedirect = "none" | "signed_in" | "failed";

/**
 * Picks up the session Supabase puts in the URL fragment after the user clicks
 * the email sign-in link, stores the access token, and strips it from the URL.
 */
export function consumeSignInRedirect(): SignInRedirect {
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const query = new URLSearchParams(window.location.search);
  const token = fragment.get("access_token");
  const failed = fragment.has("error") || query.has("error") || query.has("error_code");
  if (!token && !failed) {
    return "none";
  }
  window.history.replaceState(null, "", window.location.pathname);
  if (token) {
    setAccessToken(token);
    return "signed_in";
  }
  return "failed";
}
