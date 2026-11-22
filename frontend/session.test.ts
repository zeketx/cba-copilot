import assert from "node:assert/strict";
import { test } from "node:test";
import {
  AUTH_PREVIEW_PARAM,
  SIGN_IN_COPY,
  authPathAfterConsume,
  classifySignInRedirect,
  consumeSignInRedirect,
  getAccessToken,
  hasAuthCallback,
  noticeForRedirect,
  otpRequestBody,
} from "./src/lib/session.ts";

test("OTP requests never create a user", () => {
  const body = otpRequestBody("fan@example.com", "challenge");
  assert.equal(body.create_user, false);
  assert.equal(body.code_challenge_method, "s256");
  assert.equal(body.email, "fan@example.com");
});

test("a PKCE code in this browser is exchanged", () => {
  assert.deepEqual(
    classifySignInRedirect({
      search: "?code=pkce-one",
      hash: "",
      hasVerifier: true,
    }),
    { kind: "exchange", code: "pkce-one" },
  );
});

test("a PKCE code without a verifier is the other browser", () => {
  assert.deepEqual(
    classifySignInRedirect({
      search: "?code=pkce-one",
      hash: "",
      hasVerifier: false,
    }),
    { kind: "wrong_browser" },
  );
});

test("an implicit hash token is out of date even when a code is present", () => {
  assert.deepEqual(
    classifySignInRedirect({
      search: "?code=pkce-one",
      hash: "#access_token=stolen",
      hasVerifier: true,
    }),
    { kind: "out_of_date" },
  );
});

test("GoTrue error query is expired", () => {
  assert.deepEqual(
    classifySignInRedirect({
      search: "?error=access_denied&error_code=otp_expired",
      hash: "",
      hasVerifier: false,
    }),
    { kind: "expired" },
  );
});

test("auth_preview is a harmless UI fixture when there is no callback", () => {
  assert.deepEqual(
    classifySignInRedirect({
      search: `?${AUTH_PREVIEW_PARAM}=wrong_browser`,
      hash: "",
      hasVerifier: false,
    }),
    { kind: "wrong_browser" },
  );
  assert.deepEqual(
    classifySignInRedirect({
      search: `?${AUTH_PREVIEW_PARAM}=expired`,
      hash: "",
      hasVerifier: false,
    }),
    { kind: "expired" },
  );
  assert.deepEqual(
    classifySignInRedirect({
      search: `?${AUTH_PREVIEW_PARAM}=out_of_date`,
      hash: "",
      hasVerifier: false,
    }),
    { kind: "out_of_date" },
  );
});

test("auth_preview does not override a hash token", () => {
  assert.deepEqual(
    classifySignInRedirect({
      search: `?${AUTH_PREVIEW_PARAM}=wrong_browser`,
      hash: "#access_token=stolen",
      hasVerifier: false,
    }),
    { kind: "out_of_date" },
  );
});

test("plain landing hashes are not callbacks", () => {
  assert.equal(
    classifySignInRedirect({ search: "", hash: "#sign-in", hasVerifier: false }).kind,
    "none",
  );
  assert.equal(hasAuthCallback("", "#sign-in"), false);
  assert.equal(hasAuthCallback("?code=pkce-one", ""), true);
  assert.equal(hasAuthCallback("", "#access_token=stolen"), true);
});

test("consume strips codes and tokens and keeps the sign-in hash", () => {
  assert.equal(authPathAfterConsume("/", "#access_token=stolen"), "/");
  assert.equal(authPathAfterConsume("/", "#sign-in"), "/#sign-in");
  assert.equal(authPathAfterConsume("/", "#request-access"), "/#request-access");
});

test("consumeSignInRedirect rejects a hash token, stores nothing, and strips the URL", async () => {
  const store = new Map<string, string>();
  const storage = {
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
  };
  const location = { hash: "#access_token=stolen", search: "", pathname: "/" };
  const windowLike = {
    location,
    history: {
      replaceState(_state: unknown, _title: string, url: string) {
        const parsed = new URL(url, "https://app.test");
        location.pathname = parsed.pathname;
        location.search = parsed.search;
        location.hash = parsed.hash;
      },
    },
  };
  Object.assign(globalThis, { window: windowLike, sessionStorage: storage });
  const kind = await consumeSignInRedirect();
  assert.equal(kind, "out_of_date");
  assert.equal(getAccessToken(), null);
  assert.equal(location.hash, "");
  assert.equal(location.search, "");
});

test("product copy is the approved strings", () => {
  assert.equal(
    SIGN_IN_COPY.linkSent,
    "If this email is approved, you'll get a sign-in link shortly. Open it in this same browser within an hour. If you haven't been approved yet, you can request access.",
  );
  assert.equal(
    SIGN_IN_COPY.wrongBrowser,
    "This link only works in the browser where you asked for it. Enter your email here and we'll send a new link to this device.",
  );
  assert.equal(SIGN_IN_COPY.sendNewLink, "Send a new link here");
  assert.equal(SIGN_IN_COPY.expired, "That sign-in link expired or was already used. Send a new one.");
  assert.equal(SIGN_IN_COPY.outOfDate, "This sign-in link is out of date. Enter your email to get a new one.");
  assert.equal(SIGN_IN_COPY.requestSent, "Request sent. We'll email you if you're approved.");
  assert.equal(SIGN_IN_COPY.rateLimited, "Please try again in a little while.");
  assert.equal(noticeForRedirect("wrong_browser"), SIGN_IN_COPY.wrongBrowser);
  assert.equal(noticeForRedirect("expired"), SIGN_IN_COPY.expired);
  assert.equal(noticeForRedirect("out_of_date"), SIGN_IN_COPY.outOfDate);
  assert.equal(noticeForRedirect("none"), null);
  assert.equal(noticeForRedirect("signed_in"), null);
});
