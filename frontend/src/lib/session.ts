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

export async function requestSignInCode(email: string): Promise<void> {
  const response = await fetch(goTrueUrl("/auth/v1/otp"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: anonKey(),
    },
    body: JSON.stringify({ email, create_user: false }),
  });
  if (!response.ok) {
    throw new SignInFailed();
  }
}

export async function completeSignIn(email: string, code: string): Promise<void> {
  const response = await fetch(goTrueUrl("/auth/v1/verify"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: anonKey(),
    },
    body: JSON.stringify({ type: "email", email, token: code }),
  });
  if (!response.ok) {
    throw new SignInFailed();
  }
  const body = (await response.json()) as { access_token?: unknown };
  if (typeof body.access_token !== "string" || body.access_token === "") {
    throw new SignInFailed();
  }
  setAccessToken(body.access_token);
}
