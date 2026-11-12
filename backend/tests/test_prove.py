import json
from pathlib import Path

from app.config import Settings
from app.domain import (
    CitedAnswer,
    Claim,
    Clarification,
    DraftAnswer,
    DraftClaim,
    Refusal,
)
from app.grounding.validate import validate_draft
from evals.prove import (
    CorpusCase,
    GradeContext,
    InjectedClaimDrafter,
    extra_numbers,
    grade_case,
    load_cases,
    main,
    missing_live_settings,
    parse_numbers,
)


def _chunk(passage_id: str, article: int, section: str, text: str):
    from app.domain import Chunk

    return Chunk(
        id=passage_id,
        article_number=article,
        article_title="Test",
        section=section,
        page_start=1,
        page_end=1,
        text=text,
        source_url="https://example.test/cba.pdf#page=25",
    )


def _case(kind: str, **fields: object) -> CorpusCase:
    payload: dict[str, object] = {
        "id": kind,
        "kind": kind,
        "question": "question",
        "expected_sections": [
            {"article": 7, "section_contains": "2(e)"},
        ],
    }
    payload.update(fields)
    return CorpusCase.model_validate(payload)


def _answer(*claims: Claim) -> CitedAnswer:
    return CitedAnswer(claims=list(claims))


def _ctx(*chunks) -> GradeContext:
    return GradeContext(passages=list(chunks))


APRON = _chunk(
    "apron",
    7,
    "2(e)(4) Transaction Restrictions Table",
    "A team may not acquire a player using an Aggregated Standard Traded Player Exception.",
)
AWARDS = _chunk(
    "awards",
    29,
    "6 Games Played Requirement for Certain League Honors",
    (
        "A player needs sixty-five Regular Season games, "
        "or sixty-two games and a season-ending injury."
    ),
)
MLE = _chunk(
    "mle",
    7,
    "6(f) Taxpayer Mid-Level Salary Exception",
    "For 2023-24 the amount is 5 million dollars. Row K of the table applies at the Second Apron.",
)
EARLY = _chunk(
    "early",
    1,
    "1(t) Early Qualifying Veteran Free Agent (Early Bird)",
    (
        "Capped by the greater of 175 percent of the prior regular salary "
        "or 105 percent of the prior average player salary."
    ),
)
SALARY = _chunk(
    "salary",
    1,
    "1(lll) Salary",
    "Salary is Compensation plus other amounts. Salary does not include Unlikely Bonuses.",
)
TEAM = _chunk(
    "team",
    7,
    "4 Determination of Team Salary",
    "Team Salary is the sum of salaries attributed to a team's players.",
)
BIRD = _chunk(
    "bird",
    1,
    "1(yy) Qualifying Veteran Free Agent (Bird)",
    "A Qualifying Veteran Free Agent played the three preceding seasons.",
)


def test_graders_cover_every_case_kind() -> None:
    cases = load_cases()
    assert {case.kind for case in cases} == {
        "whole_rule",
        "exception",
        "cross_reference",
        "two_passages",
        "season_or_date",
        "computation",
        "missing_inputs",
        "definition",
        "no_evidence",
        "ambiguous",
        "bad_citation",
    }


def test_whole_rule_grader_pass_and_fail() -> None:
    case = _case("whole_rule")
    ctx = _ctx(APRON)
    good = _answer(Claim(text=APRON.text, passage_ids=["apron"]))
    assert grade_case(case, good, ctx).passed
    wrong_kind = Refusal(reason="no_evidence", message="no")
    assert not grade_case(case, wrong_kind, ctx).passed
    other = _chunk("other", 1, "1(t)", APRON.text)
    unsupported = _answer(Claim(text="A fact the passage never states.", passage_ids=["apron"]))
    assert not grade_case(case, unsupported, _ctx(APRON, other)).passed


def test_exception_grader_pass_and_fail() -> None:
    case = _case(
        "exception",
        expected_sections=[{"article": 29, "section_contains": "6"}],
        required_phrases=["sixty-five", "sixty-two", "season-ending injury"],
    )
    ctx = _ctx(AWARDS)
    good = _answer(Claim(text=AWARDS.text, passage_ids=["awards"]))
    assert grade_case(case, good, ctx).passed
    thin = _answer(
        Claim(text="A player needs sixty-five Regular Season games.", passage_ids=["awards"])
    )
    assert not grade_case(case, thin, ctx).passed


def test_cross_reference_grader_pass_and_fail() -> None:
    case = _case(
        "cross_reference",
        expected_sections=[
            {"article": 7, "section_contains": "6(f)"},
            {"article": 7, "section_contains": "2(e)"},
        ],
    )
    ctx = _ctx(MLE, APRON)
    good = _answer(
        Claim(text=MLE.text, passage_ids=["mle"]),
        Claim(text=APRON.text, passage_ids=["apron"]),
    )
    assert grade_case(case, good, ctx).passed
    one = _answer(Claim(text=MLE.text, passage_ids=["mle"]))
    assert not grade_case(case, one, ctx).passed


def test_two_passages_grader_pass_and_fail() -> None:
    case = _case(
        "two_passages",
        expected_sections=[
            {"article": 1, "section_contains": "1(lll)"},
            {"article": 7, "section_contains": "4 Determination of Team Salary"},
        ],
    )
    ctx = _ctx(SALARY, TEAM)
    both = _answer(
        Claim(text=SALARY.text, passage_ids=["salary"]),
        Claim(text=TEAM.text, passage_ids=["team"]),
    )
    assert grade_case(case, both, ctx).passed
    refuse = Refusal(reason="no_evidence", message="no")
    assert grade_case(case, refuse, ctx).passed
    one = _answer(Claim(text=SALARY.text, passage_ids=["salary"]))
    assert not grade_case(case, one, ctx).passed


def test_season_or_date_grader_pass_and_fail() -> None:
    case = _case(
        "season_or_date",
        expected_sections=[{"article": 7, "section_contains": "6(f)"}],
    )
    ctx = _ctx(MLE)
    named = _answer(Claim(text=MLE.text, passage_ids=["mle"]))
    assert grade_case(case, named, ctx).passed
    ask = Clarification(reason="ambiguous", message="which season?", claims=[named.claims[0]])
    assert grade_case(case, ask, ctx).passed
    refuse = Refusal(reason="no_evidence", message="no")
    assert not grade_case(case, refuse, ctx).passed


def test_computation_grader_pass_and_fail() -> None:
    case = _case(
        "computation",
        expected_sections=[{"article": 1, "section_contains": "1(t)"}],
        expected_number=17500000,
    )
    ctx = _ctx(EARLY)
    good = _answer(
        Claim(
            text="The cap is 17500000 under the greater-of rule in the quote.",
            passage_ids=["early"],
        )
    )
    assert grade_case(case, good, ctx).passed
    raw = _answer(Claim(text=EARLY.text, passage_ids=["early"]))
    assert not grade_case(case, raw, ctx).passed


def test_missing_inputs_grader_pass_and_fail() -> None:
    case = _case(
        "missing_inputs",
        expected_sections=[{"article": 1, "section_contains": "1(t)"}],
    )
    ctx = _ctx(EARLY)
    good = Clarification(
        reason="missing_inputs",
        message="The cited passage needs inputs the question does not give: prior salary.",
        claims=[Claim(text=EARLY.text, passage_ids=["early"])],
    )
    assert extra_numbers(good, ctx) == set()
    assert grade_case(case, good, ctx).passed
    computed = Clarification(
        reason="missing_inputs",
        message="Need salary. The cap would be 17500000.",
        claims=[Claim(text=EARLY.text, passage_ids=["early"])],
    )
    assert not grade_case(case, computed, ctx).passed
    answer = _answer(Claim(text=EARLY.text, passage_ids=["early"]))
    assert not grade_case(case, answer, ctx).passed


def test_definition_grader_pass_and_fail() -> None:
    case = _case(
        "definition",
        expected_sections=[{"article": 1, "section_contains": "1(lll)"}],
    )
    ctx = _ctx(SALARY)
    good = _answer(Claim(text=SALARY.text, passage_ids=["salary"]))
    assert grade_case(case, good, ctx).passed
    numbered = _answer(
        Claim(text=SALARY.text + " The cap is 136000000.", passage_ids=["salary"])
    )
    assert not grade_case(case, numbered, ctx).passed


def test_no_evidence_grader_pass_and_fail() -> None:
    case = _case("no_evidence", expected_sections=[])
    ctx = _ctx()
    good = Refusal(reason="no_evidence", message="no")
    assert grade_case(case, good, ctx).passed
    dropped = Refusal(reason="citations_dropped", message="dropped")
    assert not grade_case(case, dropped, ctx).passed


def test_ambiguous_grader_pass_and_fail() -> None:
    case = _case(
        "ambiguous",
        expected_sections=[
            {"article": 1, "section_contains": "1(yy)"},
            {"article": 1, "section_contains": "1(t)"},
        ],
    )
    ctx = _ctx(BIRD, EARLY)
    good = Clarification(
        reason="ambiguous",
        message="which one?",
        claims=[
            Claim(text=BIRD.text, passage_ids=["bird"]),
            Claim(text=EARLY.text, passage_ids=["early"]),
        ],
    )
    assert grade_case(case, good, ctx).passed
    winner = _answer(Claim(text=BIRD.text, passage_ids=["bird"]))
    assert not grade_case(case, winner, ctx).passed


def test_bad_citation_grader_pass_and_fail() -> None:
    case = _case(
        "bad_citation",
        injected_text="A second-apron team may aggregate salaries without limit.",
        injected_quote="this quote is not in any retrieved CBA passage",
    )
    ctx = _ctx(APRON)
    kept = _answer(
        Claim(text=case.injected_text, passage_ids=["apron"]),
    )
    assert not grade_case(case, kept, ctx).passed
    clean = _answer(Claim(text=APRON.text, passage_ids=["apron"]))
    assert grade_case(case, clean, ctx).passed
    refused = Refusal(reason="citations_dropped", message="dropped")
    assert grade_case(case, refused, ctx).passed


def test_injected_claim_wrapper_is_dropped_by_validation() -> None:
    class _Inner:
        def draft(self, question: str, passages) -> DraftAnswer:
            del question
            passage = passages[0]
            return DraftAnswer(
                claims=[
                    DraftClaim(
                        text=passage.text,
                        quote=passage.text,
                        passage_ids=[passage.id],
                    )
                ]
            )

    wrapper = InjectedClaimDrafter(
        _Inner(),
        text="A second-apron team may aggregate salaries without limit.",
        quote="this quote is not in any retrieved CBA passage",
    )
    draft = wrapper.draft("question", [APRON])
    assert draft.claims[-1].text.startswith("A second-apron team")
    result = validate_draft(draft, [APRON])
    assert isinstance(result, CitedAnswer)
    assert all(
        claim.text != "A second-apron team may aggregate salaries without limit."
        for claim in result.claims
    )


def test_offline_cli_writes_results_and_summary(capsys) -> None:
    code = main([])
    assert code == 0
    printed = capsys.readouterr().out.strip().splitlines()[-1]
    directory = Path(printed)
    results = directory / "results.json"
    summary = directory / "summary.md"
    assert results.is_file()
    assert summary.is_file()
    payload = json.loads(results.read_text(encoding="utf-8"))
    assert payload["live"] is False
    assert len(payload["cases"]) == 11
    assert "docs/phase10" not in str(directory)


def test_missing_live_settings_names_the_variable() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="",
        database_url="",
        supabase_url="",
    )
    message = missing_live_settings(settings)
    assert message is not None
    assert "OPENAI_API_KEY" in message
    assert "sk-" not in message


def test_parse_numbers_ignores_commas() -> None:
    assert 17500000 in parse_numbers("the cap is 17,500,000 dollars")
