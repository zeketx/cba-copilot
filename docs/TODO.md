# Answer one CBA question with a citation or a refusal

This list is the MVP for [cba-copilot](https://github.com/zeketx/cba-copilot). You check a box only when the acceptance evidence is on this branch. Nothing here is built. `origin/main` at `a7c5a1d` has `README.md`, `LICENSE`, and `.cursor/`. It has no product code and no corpus file.

The README proposes FastAPI, PydanticAI, Supabase, pgvector, and hybrid reciprocal rank fusion. That stack is a later choice. It is not a requirement for the first passing test.

A different folder, `/Users/ezekielmauricio/Documents/dev/github/public/cba-copilot`, is four commits ahead of `origin/main`. Those commits are unpushed and are not the baseline for these boxes.

## How to use this list

Work top to bottom. Do not start a task until the tasks it depends on are checked. Each acceptance line names the evidence that checks the box. A written plan is not that evidence.

## Decisions still open

### Who asks the first question

This is not settled. Nobody has named the user.

Recommendation. The first user is one person who must apply a printed rule from the official agreement and show a colleague the page. The job in the product is a single question that ends in a cited answer, a request for a missing fact, or a refusal. A fan chat, a trade machine, and a multi-user office app are out of this list.

What would change the recommendation. Zeke names a different operator, or the first real session shows that the user arrives with a roster spreadsheet rather than a question about the text.

### Which text is authoritative

This is not settled. The README names the 2023 NBA CBA and does not attach a file, a hash, a page count, or a term clause.

Recommendation. One official PDF is the whole corpus. Record its URL, file hash, cover date, and the clause that states its term before any answer is shown to a person. Side letters, later amendments, and a later CBA are separate documents. They stay out until someone adds them under their own hash. Unofficial markdown, fan sites, and salary-cap explainers are not sources.

An unpushed local note describes a July 2023 PDF of 676 pages, in force from 1 July 2023 through the 2029-30 season, linked from the NBPA CBA page. This session did not open that PDF. Treat those details as unverified until the hash step records them.

What would change the recommendation. The official file's own cover or term clause disagrees with that note, or Zeke adds a named side letter as a second hashed document.

## Evidence, before any stack

A passage is the only evidence record. Every passage has all of these fields. A passage that lacks any one of them is invalid.

- Stable id.
- Article number.
- Article title.
- Section as printed.
- Printed page.
- PDF viewer page.
- Exact quote.
- Source URL.
- Order in the file.

A turn has the question text, the passage ids that were retrieved, and one outcome. The outcome is an answer, a clarification, or a refusal.

An answer or a clarification has claims. Each claim has its own text and one or more passage ids. Every claim passage id has to be in the retrieved set.

A refusal has a reason and an empty claim list. It still stores the retrieved passage ids. `no_support` stores an empty id list. The reasons in this list are `no_support`, `ambiguous`, `missing_inputs`, and `citation_mismatch`. There is no `outside_corpus` reason until a task defines one.

Code reads passages in this order.

1. By article number and section as printed.
2. By printed page.
3. By words in the quote.
4. By the previous and next section in the same article, when a quote points at another section.
5. By meaning of the question, only after the word lookup above has a passing test.

No step sends model-written query language to a database.

## Checklist

### 1. Freeze the evidence record

Depends on the two decisions above staying explicit. You can start this task with the recommendations. You cannot show an answer to a person until both decisions name a real user job and a hashed file.

- [ ] Put three fixture passages in one file. Use fake quotes you write for the test. Do not copy the official agreement into git.
- [ ] Reject a fixture that omits any required field from the list above.

Acceptance. A test loads the three passages. It fails when any one required field is removed from a fourth passage. The fields are the id, the article number, the article title, the section as printed, the printed page, the viewer page, the quote, the source URL, and the order in the file.

### 2. Find a passage without a model

Depends on task 1.

- [ ] Look up a passage by article number and section as printed.
- [ ] Look up a passage by printed page.
- [ ] Look up a passage by words in the quote.
- [ ] Return no passages for a question that shares no words with the fixtures.

Acceptance. One test returns the expected passage id for a known article and section. A second test returns that same id for its printed page. A third test returns an empty list for a nonsense question. None of the tests call a network.

### 3. Answer, clarify, or refuse

Depends on task 2.

- [ ] Build one function from a question and the retrieved passages to a turn.
- [ ] Drop any claim whose passage id is not in the retrieved set. If one valid claim remains, the outcome stays an answer and keeps only that claim. If none remain, the outcome is a refusal with reason `citation_mismatch` and the retrieved ids.
- [ ] Refuse with `no_support` and an empty id list when retrieval returns nothing. The refusal has no claim.
- [ ] Return a clarification when the question omits a fact the fixture marks as required, such as the season. Every claim passage id on that clarification is in the retrieved set.

Acceptance. One test drops a bad claim, keeps one valid claim, and stays an answer. A second test refuses with `citation_mismatch` and an empty claim list when every claim cites a missing id. A third test asserts that a `no_support` refusal has no claim text and no passage ids. A fourth test omits the season, expects a clarification, and checks that every claim passage id was retrieved.

### 4. More than one clause

Depends on task 3.

- [ ] Add a fixture whose quote tells the reader to apply another section, and include that other section as its own passage.
- [ ] Return both passage ids when the answer uses both quotes.
- [ ] Add one passage that contains a fake general rule and a fake exception sentence. A question about the exception case must quote the exception sentence, not only the general rule.
- [ ] Refuse with `ambiguous` when two passages match and the fixtures do not say which one controls. Store both retrieved ids, leave the claim list empty, and do not pick a winner.

Acceptance. The cross-reference test fails if either passage id is missing. The exception test fails if the claim text does not contain the fixture's exception sentence. The ambiguity test fails unless the reason is `ambiguous`, the claim list is empty, and both passage ids are stored on the turn.

### 5. Dates and numbers

Depends on task 3. Task 4 can land beside this task only if it does not change the turn fields from task 3.

- [ ] Add two fixtures that state different seasons or different effective dates. If the question names one of them, the answer uses that passage and names it. If the question names neither, ask which one the user means.
- [ ] For a calculation, compute only when every input is in the question or in a retrieved quote. Otherwise refuse with `missing_inputs`.
- [ ] Keep calculation fixtures numeric and fake. The expected result is the arithmetic of those fake inputs. It is not a real cap figure, and it is not legal advice.

Acceptance. A test with inputs `2` and `10` expects `20` and cites the fixture that states the operation. A test that omits one input expects `missing_inputs` and no computed number. A test whose quote is a definition expects the quote back and does not emit a number the quote does not contain. A test with two dated passages expects the named passage when the question names a date, and a clarification when it does not.

### 6. Time and cost on the fixture path

Depends on tasks 3, 4, and 5.

- [ ] Log the wall time of one fixture question and the count of model calls. The fixture path's count is zero.
- [ ] Record the machine the time was measured on.

Proposed threshold. A fixture question finishes in under 2 seconds on a laptop, with no network. This number is a proposal. It is not a measurement.

Acceptance. The log for the checked run shows the machine, the elapsed time, and zero model calls. Do not check this box from a guess.

### 7. Choose a store and a drafter

Depends on task 6.

- [ ] Repeat the tests from tasks 1 through 5 against the store you pick. The README stack is allowed only if those tests pass unchanged.
- [ ] If a paid model or a hosted database is required for that run, stop and ask Zeke before spending money.
- [ ] Keep the official PDF out of git. Store the hash and the URL outside the PDF bytes.

Acceptance. The same tests pass, the PDF is not in the commit, and any new dependency is named in the commit message with what it does that the fixture path could not do in a small module.

### 8. Check one question against the hashed file

Depends on task 7, and on the file decision being closed. The hash, the URL, the cover date, and the term clause have to be recorded from the file itself.

- [ ] Zeke picks one question. Run it on the hashed PDF.
- [ ] Write a transcript beside the download, not in git. Include the outcome, the article, the section, both pages, the quote, the passage ids, the hash, the URL, the cover date, and the term-clause quote.
- [ ] A person confirms that the quote and the term clause appear on the named pages of that file.

Acceptance. The gitignored transcript exists, and a committed note records the hash, the article, the section, both page numbers, and the outcome type. The commit does not add the PDF or the official sentences. Do not check this box from a plan.

## Question categories

These are the risks to test. They are not sample answers, and they do not cite a real article. The fixture for each one is named in the tasks above.

- One section contains the whole rule. Task 2.
- The same section contains an exception. Task 4.
- A section points at another section. Task 4.
- The answer needs two passages. Task 4.
- The rule depends on the season or the effective date. Task 5.
- The quote states an operation and the question supplies every input. Task 5.
- The quote states an operation and one input is missing. Task 5.
- The question asks what a term means, and no number is required. Task 5.
- The corpus has no passage for the question. Task 3, reason `no_support`.
- Two passages match and neither says it controls. Task 4, reason `ambiguous`.
- A draft claim cites a passage that does not contain the claim. Task 3, reason `citation_mismatch`.

Proposed threshold. Each category has one passing fixture before a person sees an answer drawn from the official PDF. Task 8 is that first look at the file. Do not treat a percentage of legal accuracy as a gate. This plan did not grade legal conclusions.

## Not in this list

Leave these out until the checklist above is checked. Accounts, saved chats, a trade checker, a comparison across CBA editions, a glossary product, scraping fan sites, and deploying a hosted service are not required to answer one question with a citation or a refusal.
