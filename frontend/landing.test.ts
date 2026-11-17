import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  REQUEST_ACCESS_HREF,
  SIGN_IN_HREF,
  gateViewFromHash,
} from "./src/components/landing/access.ts";
import { BALL_LAYER, COURT_LAYERS } from "./src/components/landing/layers.ts";

const root = path.dirname(fileURLToPath(import.meta.url));
const assets = path.join(root, "src/assets/landing");
const src = path.join(root, "src");

test("logged-out visitors get the landing page", () => {
  const app = readFileSync(path.join(src, "App.tsx"), "utf8");
  assert.match(app, /sessionToken === null \? \(/);
  assert.match(app, /<LandingPage onRequestAccess=\{openRequestAccess\} onSignIn=\{openSignIn\} \/>/);
  assert.doesNotMatch(app, /sessionToken === null \? \(\s*<div className="h-dvh"/);
  const hero = readFileSync(path.join(src, "components/landing/Hero.tsx"), "utf8");
  assert.match(hero, /The CBA, answered/);
  assert.match(hero, /<h1 className="landing-headline">The CBA, answered\.<\/h1>/);
});

test("Request access opens the request view and Sign in opens login", () => {
  assert.equal(REQUEST_ACCESS_HREF, "#request-access");
  assert.equal(SIGN_IN_HREF, "#sign-in");
  assert.equal(gateViewFromHash("#request-access"), "request");
  assert.equal(gateViewFromHash("#sign-in"), "login");
  assert.equal(gateViewFromHash(""), null);

  const hero = readFileSync(path.join(src, "components/landing/Hero.tsx"), "utf8");
  assert.match(hero, /href=\{REQUEST_ACCESS_HREF\}/);
  assert.match(hero, /Request access/);
  assert.match(hero, /href=\{SIGN_IN_HREF\}/);
  assert.match(hero, /onRequestAccess\(\)/);
  assert.match(hero, /onSignIn\(\)/);
  assert.doesNotMatch(hero, /Get access/);

  const app = readFileSync(path.join(src, "App.tsx"), "utf8");
  assert.match(app, /function openRequestAccess\(\) \{/);
  assert.match(app, /function openSignIn\(\) \{/);
  assert.match(app, /openGate\("request"\)/);
  assert.match(app, /openGate\("login"\)/);
});

test("illustrative example uses the minimum-salary case, not second-apron", () => {
  const example = readFileSync(path.join(src, "components/landing/Example.tsx"), "utf8");
  assert.match(example, /Illustrative example/);
  assert.match(example, /2023-24, 0 YOS/);
  assert.match(example, /What is the minimum salary for a player with 0 years of service\?/);
  assert.match(example, /1,017,781/);
  assert.match(example, /corpus_cases\.yaml/);
  assert.doesNotMatch(example, /second-apron/);
});

test("court layers list only the pieces the page uses, with sizes", () => {
  assert.deepEqual(
    COURT_LAYERS.map((layer) => layer.id),
    ["stands", "court", "hoop-back", "hoop-front"],
  );
  for (const layer of COURT_LAYERS) {
    assert.ok(layer.width > 0);
    assert.ok(layer.height > 0);
    assert.equal(existsSync(path.join(assets, layer.file)), true, layer.file);
  }
  const hoop = COURT_LAYERS.find((layer) => layer.id === "hoop-back");
  assert.equal(hoop?.mobile.height, "min(400px, 42vh)");
  assert.equal(existsSync(path.join(assets, BALL_LAYER.file)), true);
  assert.equal(existsSync(path.join(assets, "court-angle.webp")), false);
  assert.equal(existsSync(path.join(assets, "ball-sheet-source.webp")), false);
});
