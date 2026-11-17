import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { GET_ACCESS_HREF } from "./src/components/landing/access.ts";
import { BALL_LAYER, COURT_LAYERS } from "./src/components/landing/layers.ts";

const root = path.dirname(fileURLToPath(import.meta.url));
const assets = path.join(root, "src/assets/landing");
const src = path.join(root, "src");

test("logged-out visitors get the landing page", () => {
  const app = readFileSync(path.join(src, "App.tsx"), "utf8");
  assert.match(app, /sessionToken === null \? \(/);
  assert.match(app, /<LandingPage onGetAccess=\{openSignIn\} \/>/);
  assert.doesNotMatch(app, /sessionToken === null \? \(\s*<div className="h-dvh"/);
  const landing = readFileSync(path.join(src, "components/landing/LandingPage.tsx"), "utf8");
  assert.match(landing, /<h1|Hero /);
  const hero = readFileSync(path.join(src, "components/landing/Hero.tsx"), "utf8");
  assert.match(hero, /The CBA, answered/);
  assert.match(hero, /<h1 className="landing-headline">The CBA, answered\.<\/h1>/);
});

test("Get access points at the magic-link sign-in flow", () => {
  assert.equal(GET_ACCESS_HREF, "#sign-in");
  const hero = readFileSync(path.join(src, "components/landing/Hero.tsx"), "utf8");
  assert.match(hero, /href=\{GET_ACCESS_HREF\}/);
  assert.match(hero, /onGetAccess\(\)/);
  const app = readFileSync(path.join(src, "App.tsx"), "utf8");
  assert.match(app, /function openSignIn\(\) \{/);
  assert.match(app, /setGateView\("login"\)/);
  assert.match(app, /setSignInOpen\(true\)/);
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
  assert.equal(existsSync(path.join(assets, BALL_LAYER.file)), true);
  assert.equal(existsSync(path.join(assets, "court-angle.webp")), false);
  assert.equal(existsSync(path.join(assets, "ball-sheet-source.webp")), false);
});
