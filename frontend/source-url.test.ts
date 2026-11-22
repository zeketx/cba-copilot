import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  FILING_IFRAME_SANDBOX,
  OFFICIAL_PDF_ORIGIN,
  PDF_IFRAME_SANDBOX,
  allowedSourceUrl,
  officialPdfOrigin,
} from "./src/lib/source-url.ts";

const root = path.dirname(fileURLToPath(import.meta.url));

test("only https URLs on the official PDF origin are allowed", () => {
  const corpus = JSON.parse(readFileSync(path.join(root, "../data/corpus.json"), "utf8")) as {
    pdf_url: string;
  };
  const origin = officialPdfOrigin();
  assert.equal(origin, OFFICIAL_PDF_ORIGIN);
  assert.equal(origin, new URL(corpus.pdf_url).origin);
  assert.equal(
    allowedSourceUrl(`${origin}/cba.pdf#page=24`),
    `${origin}/cba.pdf#page=24`,
  );
  assert.equal(allowedSourceUrl("http://imgix.cosmicjs.com/cba.pdf"), null);
  assert.equal(allowedSourceUrl("javascript:alert(1)"), null);
  assert.equal(allowedSourceUrl("https://evil.example/cba.pdf"), null);
  assert.equal(allowedSourceUrl("not a url"), null);
});

test("PDF iframe is sandboxed without same-origin and filing viewer drops it", () => {
  assert.equal(PDF_IFRAME_SANDBOX.includes("allow-same-origin"), false);
  assert.equal(FILING_IFRAME_SANDBOX, "");
  const panel = readFileSync(path.join(root, "src/components/chat/SourcePanel.tsx"), "utf8");
  const viewer = readFileSync(path.join(root, "src/components/chat/FilingViewer.tsx"), "utf8");
  const answer = readFileSync(path.join(root, "src/components/chat/CitedAnswer.tsx"), "utf8");
  assert.match(panel, /sandbox=\{PDF_IFRAME_SANDBOX\}/);
  assert.match(panel, /allowedSourceUrl/);
  assert.match(viewer, /sandbox=\{FILING_IFRAME_SANDBOX\}/);
  assert.doesNotMatch(viewer, /allow-same-origin/);
  assert.match(answer, /allowedSourceUrl/);
});
