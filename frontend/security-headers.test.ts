import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import type { AddressInfo } from "node:net";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer, preview } from "vite";
import { contentSecurityPolicy, originOf, securityHeaders } from "./security-headers.ts";

const root = path.dirname(fileURLToPath(import.meta.url));
const configFile = path.join(root, "vite.config.ts");
const SUPABASE = "https://proj.supabase.co";
const API = "https://api.example.test";

function hosts(policy: string): Set<string> {
  return new Set(policy.match(/https?:\/\/[^\s;]+/g) ?? []);
}

function pdfOrigin(): string {
  const corpus = JSON.parse(readFileSync(path.join(root, "../data/corpus.json"), "utf8")) as {
    pdf_url: string;
  };
  return new URL(corpus.pdf_url).origin;
}

test("the policy allows the supabase, api, and pdf origins only", () => {
  const policy = contentSecurityPolicy({
    supabaseUrl: `${SUPABASE}/auth/v1`,
    apiBase: `${API}/api`,
    pdfUrl: `${pdfOrigin()}/file.pdf`,
  });
  assert.deepEqual(hosts(policy), new Set([SUPABASE, API, pdfOrigin()]));
  assert.equal(policy.includes("*"), false);
  assert.match(policy, /frame-ancestors 'none'/);
  assert.match(policy, /script-src 'self'/);
  assert.equal(policy.includes("/auth/v1"), false);
  assert.equal(policy.includes("/file.pdf"), false);
  assert.equal(originOf("javascript:alert(1)"), null);
  assert.equal(originOf(""), null);

  const headers = securityHeaders({
    supabaseUrl: `${SUPABASE}/auth/v1`,
    apiBase: `${API}/api`,
    pdfUrl: `${pdfOrigin()}/file.pdf`,
  });
  assert.equal(headers["Content-Security-Policy"], policy);
  assert.equal(headers["X-Frame-Options"], "DENY");
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["Referrer-Policy"], "strict-origin-when-cross-origin");
  assert.equal(headers["Strict-Transport-Security"], "max-age=31536000; includeSubDomains");
});

test("hosted preview sends the headers and the dev server does not", { timeout: 120_000 }, async () => {
  assert.ok(existsSync(path.join(root, "dist", "index.html")), "run pnpm build before pnpm test");
  const previous = {
    supabase: process.env.VITE_SUPABASE_URL,
    api: process.env.VITE_API_BASE,
  };
  process.env.VITE_SUPABASE_URL = SUPABASE;
  process.env.VITE_API_BASE = API;
  const dev = await createServer({
    configFile,
    root,
    mode: "development",
    server: { host: "127.0.0.1", port: 0 },
  });
  try {
    await dev.listen();
    const devAddress = dev.httpServer?.address() as AddressInfo;
    const devResponse = await fetch(`http://127.0.0.1:${devAddress.port}/`);
    assert.equal(devResponse.status, 200);
    assert.equal(devResponse.headers.get("strict-transport-security"), null);
    assert.equal(devResponse.headers.get("content-security-policy"), null);
  } finally {
    await dev.close();
  }

  const hosted = await preview({
    configFile,
    root,
    mode: "production",
    preview: { host: "127.0.0.1", port: 0 },
  });
  try {
    const address = hosted.httpServer?.address() as AddressInfo;
    const response = await fetch(`http://127.0.0.1:${address.port}/`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("x-frame-options"), "DENY");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("referrer-policy"), "strict-origin-when-cross-origin");
    assert.equal(
      response.headers.get("strict-transport-security"),
      "max-age=31536000; includeSubDomains",
    );
    const policy = response.headers.get("content-security-policy") ?? "";
    assert.match(policy, /frame-ancestors 'none'/);
    assert.equal(policy.includes("*"), false);
    assert.deepEqual(hosts(policy), new Set([SUPABASE, API, pdfOrigin()]));
  } finally {
    await hosted.close();
    if (previous.supabase === undefined) {
      delete process.env.VITE_SUPABASE_URL;
    } else {
      process.env.VITE_SUPABASE_URL = previous.supabase;
    }
    if (previous.api === undefined) {
      delete process.env.VITE_API_BASE;
    } else {
      process.env.VITE_API_BASE = previous.api;
    }
  }
});
