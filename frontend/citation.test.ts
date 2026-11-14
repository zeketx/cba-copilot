import assert from "node:assert/strict";
import { test } from "node:test";
import { compactCitationLabel, sectionCode } from "./src/lib/citation.ts";

test("sectionCode keeps the number and the nested subsection", () => {
  assert.equal(sectionCode("2. Salary Cap Exceptions / (f)(1)(i) Room Mid-Level"), "2(f)(1)(i)");
  assert.equal(sectionCode("1(lll) Salary"), "1(lll)");
  assert.equal(sectionCode("1(rr) Non-Qualifying Veteran Free Agent (Non-Bird)"), "1(rr)");
  assert.equal(sectionCode("6 Games Played Requirement for Certain League Honors"), "6");
  assert.equal(sectionCode("Exhibit A / 3. Compensation"), "3");
  assert.equal(sectionCode("Preamble"), null);
});

test("compactCitationLabel reads like Art. VII §2(f) p.195", () => {
  assert.equal(
    compactCitationLabel({ articleNumber: 7, section: "2. Salary Cap Exceptions / (f)", pageStart: 195 }),
    "Art. VII §2(f) p.195",
  );
  assert.equal(
    compactCitationLabel({ articleNumber: null, section: "Exhibit A / 3. Compensation", pageStart: 592 }),
    "Exhibit A §3 p.592",
  );
  assert.equal(compactCitationLabel({ articleNumber: 29, section: "Preamble", pageStart: null }), "Art. XXIX");
});
