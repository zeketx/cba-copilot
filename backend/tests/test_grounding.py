from pathlib import Path

from app.domain import AMBIGUOUS_MESSAGE, Chunk, DraftAnswer, DraftClaim
from app.grounding.validate import validate_draft
from ingest.cba_text import chunk_cba_text

_EQVFA_FIXTURE = Path(__file__).parent / "fixtures" / "article_vii_6b_layout.txt"


def _passage(passage_id: str, text: str = "Second apron trade limits.") -> Chunk:
    return Chunk(
        id=passage_id,
        article_number=7,
        article_title="Aprons",
        section="2(e)",
        page_start=190,
        page_end=191,
        text=text,
        source_url="https://example.test/cba.pdf#page=214",
    )


def _claim(
    text: str,
    passage_ids: list[str],
    quote: str = "Second apron trade limits.",
) -> DraftClaim:
    return DraftClaim(text=text, quote=quote, passage_ids=passage_ids)


def test_keeps_a_claim_cited_to_a_retrieved_passage() -> None:
    passage = _passage("p1")
    result = validate_draft(
        DraftAnswer(claims=[_claim("No aggregation.", ["p1"])]),
        [passage],
    )
    assert result.kind == "answer"
    assert result.claims[0].passage_ids == ["p1"]
    assert result.claims[0].quote == "Second apron trade limits."


def test_keeps_a_claim_when_the_normalized_quote_is_in_the_passage() -> None:
    passage = _passage("p1", "Second   apron\ntrade limits.")
    result = validate_draft(
        DraftAnswer(
            claims=[_claim("No aggregation.", ["p1"], quote="  Second apron trade limits.  ")]
        ),
        [passage],
    )
    assert result.kind == "answer"
    assert result.claims[0].text == "No aggregation."


def test_drops_a_claim_whose_quote_is_not_in_the_cited_passage() -> None:
    result = validate_draft(
        DraftAnswer(
            claims=[
                _claim("Invented.", ["p1"], quote="not in the passage"),
                _claim("Clean.", ["p1"]),
            ]
        ),
        [_passage("p1")],
    )
    assert result.kind == "answer"
    assert [claim.text for claim in result.claims] == ["Clean."]


def test_drops_a_claim_with_any_unknown_citation() -> None:
    result = validate_draft(
        DraftAnswer(
            claims=[
                _claim("Mixed.", ["p1", "missing"]),
                _claim("Clean.", ["p1"]),
            ]
        ),
        [_passage("p1")],
    )
    assert result.kind == "answer"
    assert [claim.text for claim in result.claims] == ["Clean."]


def test_refusal_when_every_claim_is_dropped() -> None:
    result = validate_draft(
        DraftAnswer(claims=[_claim("Invented.", ["nope"])]),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "citations_dropped"


def test_refusal_when_every_quote_misses_the_passage() -> None:
    result = validate_draft(
        DraftAnswer(claims=[_claim("Invented.", ["p1"], quote="absent span")]),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "citations_dropped"


def test_drops_an_empty_quote() -> None:
    result = validate_draft(
        DraftAnswer(claims=[_claim("Empty quote.", ["p1"], quote="   ")]),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "citations_dropped"


def test_refusal_when_the_drafter_marks_insufficient_evidence() -> None:
    result = validate_draft(
        DraftAnswer(status="insufficient_evidence", claims=[]),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"


def test_ambiguous_with_two_retrieved_passages_is_a_clarification() -> None:
    result = validate_draft(
        DraftAnswer(
            status="ambiguous",
            claims=[
                _claim("Season A.", ["p1"]),
                _claim("Season B.", ["p2"]),
            ],
        ),
        [_passage("p1"), _passage("p2")],
    )
    assert result.kind == "clarification"
    assert result.reason == "ambiguous"
    assert result.message == AMBIGUOUS_MESSAGE
    cited = {passage_id for claim in result.claims for passage_id in claim.passage_ids}
    assert cited == {"p1", "p2"}


def test_ambiguous_with_one_valid_passage_drops_citations() -> None:
    result = validate_draft(
        DraftAnswer(
            status="ambiguous",
            claims=[
                _claim("Kept.", ["p1"]),
                _claim("Gone.", ["missing"]),
            ],
        ),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "citations_dropped"


def test_missing_inputs_with_a_name_is_a_clarification() -> None:
    result = validate_draft(
        DraftAnswer(
            status="missing_inputs",
            claims=[_claim("Needs a salary.", ["p1"])],
            missing_inputs=["  prior salary  ", ""],
        ),
        [_passage("p1")],
    )
    assert result.kind == "clarification"
    assert result.reason == "missing_inputs"
    assert "prior salary" in result.message
    assert result.claims[0].passage_ids == ["p1"]


def test_missing_inputs_with_no_names_is_no_evidence() -> None:
    result = validate_draft(
        DraftAnswer(
            status="missing_inputs",
            claims=[_claim("Needs a salary.", ["p1"])],
            missing_inputs=["  ", ""],
        ),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"


def test_compact_section_label_resolves_to_the_retrieved_id() -> None:
    passage = _passage("uuid-early", "Early Qualifying Veteran Free Agent 175 percent.")
    passage = passage.model_copy(
        update={"section": "6(b)(3)(i) Early Qualifying Veteran Free Agent"}
    )
    result = validate_draft(
        DraftAnswer(
            claims=[
                _claim(
                    "The first-year cap is 175 percent.",
                    ["6(b)(3)(i)"],
                    quote="Early Qualifying Veteran Free Agent 175 percent.",
                )
            ]
        ),
        [passage],
    )
    assert result.kind == "answer"
    assert result.claims[0].passage_ids == ["uuid-early"]


def test_hyphen_break_quote_matches_the_joined_passage() -> None:
    passage = _passage(
        "p1",
        "If the player is an Early Qualifying Veteran Free Agent, the new Player Contract.",
    )
    result = validate_draft(
        DraftAnswer(
            claims=[
                _claim(
                    "Early Bird status.",
                    ["p1"],
                    quote="Early-\nQualifying Veteran Free Agent",
                )
            ]
        ),
        [passage],
    )
    assert result.kind == "answer"


def test_general_rule_and_exception_quote_can_span_cited_passages() -> None:
    general = _passage(
        "general",
        "A Veteran Free Agent may enter into a new Player Contract with his Prior Team.",
    )
    exception = _passage(
        "early",
        "If the player is an Early Qualifying Veteran Free Agent, the first year is capped.",
    )
    quote = (
        "A Veteran Free Agent may enter into a new Player Contract with his Prior Team. "
        "If the player is an Early Qualifying Veteran Free Agent, the first year is capped."
    )
    result = validate_draft(
        DraftAnswer(
            claims=[
                DraftClaim(
                    text="Quote the rule and the Early Bird cap together.",
                    quote=quote,
                    passage_ids=["general", "early"],
                )
            ]
        ),
        [general, exception],
    )
    assert result.kind == "answer"


def test_early_qualifying_fixture_accepts_compact_label_and_hyphen_quote() -> None:
    chunks = chunk_cba_text(
        _EQVFA_FIXTURE.read_text(encoding="utf-8"),
        source_url="https://example.test/cba.pdf",
        page_offset=24,
    )
    early = next(chunk for chunk in chunks if chunk.section.startswith("6(b)(3)(i)"))
    result = validate_draft(
        DraftAnswer(
            claims=[
                DraftClaim(
                    text="Early Bird first-year salary is the greater of 175 or 105 percent.",
                    quote="If the player is an Early-\nQualifying Veteran Free Agent",
                    passage_ids=["6(b)(3)(i)"],
                )
            ]
        ),
        [early],
    )
    assert result.kind == "answer"
    assert result.claims[0].passage_ids == [early.id]


def test_minimum_salary_compact_label_keeps_a_hyphen_quote() -> None:
    passage = Chunk(
        id="min-uuid",
        article_number=7,
        article_title="Exceptions to the Salary Cap",
        section="6(i) Minimum Player Salary Exception",
        page_start=240,
        page_end=240,
        text=(
            "A Team may sign or acquire a player to a one (1) or two (2) year "
            "Contract that provides in the first Salary Cap Year for the "
            "Minimum-\nPlayer Salary, with no bonuses."
        ),
        source_url="https://example.test/cba.pdf#page=264",
    )
    result = validate_draft(
        DraftAnswer(
            claims=[
                DraftClaim(
                    text="A minimum-salary deal can run one or two seasons.",
                    quote="Minimum Player Salary, with no bonuses",
                    passage_ids=["6(i)"],
                )
            ]
        ),
        [passage],
    )
    assert result.kind == "answer"
    assert result.claims[0].passage_ids == ["min-uuid"]
