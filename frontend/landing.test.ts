import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  REQUEST_ACCESS_HREF,
  SIGN_IN_HREF,
  gateViewFromHash,
} from "./src/components/landing/access.ts";
import { CBA_THREAD_EXAMPLES } from "./src/components/landing/cba-examples.ts";

const root = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(root, "src");

test("logged-out visitors get the redesigned landing page", () => {
  const app = readFileSync(path.join(src, "App.tsx"), "utf8");
  assert.match(app, /sessionToken === null \? \(/);
  assert.match(app, /<LandingPage onRequestAccess=\{openRequestAccess\} onSignIn=\{openSignIn\} \/>/);

  const page = readFileSync(path.join(src, "components/landing/LandingPage.tsx"), "utf8");
  assert.match(page, /2023 NBA CBA research for/);
  assert.match(page, /data-moment="letters-assemble"/);
  assert.match(page, /Citation checks/);
});

test("Request access opens the request view and Sign in opens login", () => {
  assert.equal(REQUEST_ACCESS_HREF, "#request-access");
  assert.equal(SIGN_IN_HREF, "#sign-in");
  assert.equal(gateViewFromHash("#request-access"), "request");
  assert.equal(gateViewFromHash("#sign-in"), "login");
  assert.equal(gateViewFromHash(""), null);

  const page = readFileSync(path.join(src, "components/landing/LandingPage.tsx"), "utf8");
  assert.match(page, /href=\{REQUEST_ACCESS_HREF\}/);
  assert.match(page, /Request access/);
  assert.match(page, /href=\{SIGN_IN_HREF\}/);
  assert.match(page, /onRequestAccess\(\)/);
  assert.match(page, /onSignIn\(\)/);

  const app = readFileSync(path.join(src, "App.tsx"), "utf8");
  assert.match(app, /function openRequestAccess\(\) \{/);
  assert.match(app, /function openSignIn\(\) \{/);
  assert.match(app, /openGate\("request"\)/);
  assert.match(app, /openGate\("login"\)/);
});

test("workspace examples include verified 2023 CBA citations with PDF page offsets", () => {
  assert.ok(CBA_THREAD_EXAMPLES.length >= 3);
  for (const example of CBA_THREAD_EXAMPLES) {
    assert.ok(example.question.length > 10);
    assert.ok(example.claims.length >= 2);
    assert.ok(example.citations.length >= 1);
    for (const citation of example.citations) {
      assert.ok(citation.pdfPage > 24);
      assert.ok(citation.passage.length > 80);
    }
  }
});
