# Draft question review

Offline check of `backend/evals/draft_questions.yaml` against the official 2023 CBA PDF. No draft was promoted to `questions.yaml`. Final accept/reject is the owner's.

The file has **33** drafts (the follow-up said 30). Labels were checked on both parsers:

- **Layout** (`ingest/cba_text.py`, `pdftotext -layout`): 2030 chunks after the nested-marker fix. This is what `evals.embed_bench --check-questions` uses.
- **Markdown ingest** (`ingest/chunker.py`, the live `ingest load` path): 1739 chunks.

`STRICT` here means the expected article + `section_contains` matched at least one chunk. It is not a live retrieval or answer-quality score.

## Summary

| Verdict | Count | IDs |
| --- | ---: | --- |
| Accept | 25 | see list below |
| Accept after a label tweak | 2 | `qualifying-veteran-cap-hold`, `exhibit-a-upc-term` |
| Overlaps a live `questions.yaml` case | 6 | Bird / Salary / second apron / taxpayer MLE / 65-game |
| Layout-only miss | 1 | `exhibit-a-upc-term` (already in the tweak row; markdown matches) |

`uv run python -m evals.embed_bench --check-questions --questions evals/draft_questions.yaml` reports **one** `UNMATCHED`: `exhibit-a-upc-term`. Every other draft matches the layout corpus.

## Parser notes that affect a few keys

- Nested markers such as `(3) (i)` now compact to `6(b)(3)(i)` on layout. Parent needles such as `4(d)(1)` therefore also match `4(d)(1)(i)` and `4(d)(1)(ii)`.
- Layout stores exhibits as a few large blobs (`Exhibit A`, `Exhibit A part 2`, …). Markdown ingest splits Exhibit A into paragraph chunks, including `Exhibit A / 1. Term`.
- `sign-and-trade-permission` uses a spaced needle `8(e) (1)`. `section_matches` already folds that to `8(e)(1)`, and both parsers hit the body chunk.

## Recommendations

### Accept

These keys exist, the answer note is in the matching chunk, and they are not a near-copy of a live question.

| ID | Expected | Pages | Note |
| --- | --- | --- | --- |
| `non-bird-definition` | I `1(rr)` | 6 | Completes the Bird / Early Bird / Non-Bird set. |
| `team-salary-definition` | I `1(uuu)` | 11 | Definition chunk. Question overlap is thin (`salary`, `team`); wording is still the right ask. |
| `room-definition` | I `1(kkk)` | 9 | |
| `minimum-team-salary-definition` | I `1(ll)` | 5 | The definition itself points at VII 2(b). That is what the quote says; do not retarget to 2(c) without reading the PDF. |
| `rookie-scale-contract-definition` | I `1(jjj)` | 9 | |
| `salary-cap-calculation` | VII `2(a)(1) For each` | 169–170 | Needle is already pinned to the formula sentence. |
| `apron-team-salary` | VII `2(e)(1) “Apron Team Salary”` | 186–187 | |
| `veteran-exception-opens` | VII `6(b) Veteran` | 231 | Hits the parent 6(b) heading, which is where the 12:01 p.m. start lives. |
| `bird-resign-first-year` | VII `6(b)(1)` | 231 | |
| `non-bird-first-year` | VII `6(b)(2) If` | 231–232 | The `If` pin avoids 6(b)(2)(ii) leftovers. After the parser fix, Early Bird is no longer inside this chunk. |
| `biannual-consecutive-years` | VII `6(d)(3)` | 235 | |
| `non-taxpayer-mle-size` | VII `6(e)(1)` | 236 | |
| `room-mle-closes-others` | VII `6(g)(3)` | 239 | |
| `minimum-salary-exception-length` | VII `6(i)` | 240 | |
| `standard-traded-player-match` | VII `6(j)(1)(i)` | 240 | |
| `aggregated-traded-player-match` | VII `6(j)(1)(ii)` | 240 | |
| `exceptions-do-not-stack` | VII `6(m)` | 247 | |
| `two-way-excluded-from-team-salary` | VII `4(j)` | 225 | |
| `exhibit-10-excluded` | VII `4(k)` | 225 | |
| `trade-cash-limit` | VII `8(a)` | 260 | |
| `sign-and-trade-permission` | VII `8(e) (1)` | 262 | |
| `two-way-salary-rate` | II `11(a)(ii)` | 50 | |
| `rookie-scale-protection` | VIII `1(c)(ii)` | 292–293 | |
| `exhibit-e-summer-league` | Exhibit E | printed E-1 | Layout is one exhibit blob; markdown is the titled notice. Both contain the summer-league sentence. |
| `exhibit-i2-prohibited-substances` | Exhibit I-2 | 649–654 | Layout one blob; markdown splits by category. `match: any` is fine. |

The table above is the accept set. It excludes the overlap and tweak cases.

### Accept after a label tweak

**`qualifying-veteran-cap-hold`** — needle `4(d)(1)` matches six layout/markdown children (`4(d)(1)(i)`, `4(d)(1)(ii)`, …). The note is the 150% hold, which is `4(d)(1)(i)` (printed 217). `4(d)(1)(ii)` is the 250% Rookie Scale option-year hold. Pin the key to `4(d)(1)(i)` before promoting.

**`exhibit-a-upc-term`** — markdown ingest already has `Exhibit A / 1. Term`. Layout does not: Exhibit A is `Exhibit A` plus `part 2`…`part 5`. `--check-questions` will keep reporting `UNMATCHED` until layout splits exhibits or the check uses the ingest parser. Recommend accept for the live ingest path, and either retarget the check or split exhibits in `cba_text.py` later.

### Overlaps a live question (defer or replace)

Do not add these as extra rows unless the owner wants the live set to drop the broader question.

| Draft | Overlaps | Suggestion |
| --- | --- | --- |
| `bird-rights-definition` | `bird-vs-early-bird` / I `1(yy)` | Clearer single-term ask. Could replace the Bird half of the live pair. |
| `early-bird-definition` | `bird-vs-early-bird` / I `1(t)` | Same for Early Bird. |
| `salary-excludes-unlikely-bonuses` | `cap-inclusions` / I `1(lll)`, and the phase 10 definition case | Keep as a definition-only sibling only if `cap-inclusions` stays the two-passage Team Salary ask. |
| `second-apron-transaction-table` | `second-apron-trade` / VII `2(e)` | More precise (`2(e)(4)`). Good replacement for the live needle, not a second question. |
| `taxpayer-mle-size` | `taxpayer-mle-second-apron` / VII `6(f)` | The live question is the second-apron change; this one is amount + term. Both are valid; they share `6(f)`. |
| `awards-sixty-five-games` | `sixty-five-game` / XXIX `6`, and the phase 10 exception case | The draft names the 62-game exception in the note. Better as the exception eval than as a second retrieval question. |

### Not wrong, but easy to confuse

- `veteran-exception-opens` vs `bird-resign-first-year` vs `non-bird-first-year`: three different 6(b) facts. Keep all three if the owner wants coverage; they are not duplicates of each other.
- `two-way-salary-rate` (II 11) vs `two-way-excluded-from-team-salary` (VII 4(j)): rate vs cap treatment. Keep both.

## What was not done

- No draft was copied into `questions.yaml`.
- No live retrieval or paid-model answer run.
- The owner still decides which overlap rows replace a live question.
