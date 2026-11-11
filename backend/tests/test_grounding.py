from app.domain import Chunk, Claim, DraftAnswer
from app.grounding.validate import validate_draft


def _passage(passage_id: str) -> Chunk:
    return Chunk(
        id=passage_id,
        article_number=7,
        article_title="Aprons",
        section="2(e)",
        page_start=190,
        page_end=191,
        text="Second apron trade limits.",
        source_url="https://example.test/cba.pdf#page=214",
    )


def test_keeps_a_claim_cited_to_a_retrieved_passage() -> None:
    passage = _passage("p1")
    result = validate_draft(
        DraftAnswer(claims=[Claim(text="No aggregation.", passage_ids=["p1"])]),
        [passage],
    )
    assert result.kind == "answer"
    assert result.claims[0].passage_ids == ["p1"]


def test_drops_a_claim_with_any_unknown_citation() -> None:
    result = validate_draft(
        DraftAnswer(
            claims=[
                Claim(text="Mixed.", passage_ids=["p1", "missing"]),
                Claim(text="Clean.", passage_ids=["p1"]),
            ]
        ),
        [_passage("p1")],
    )
    assert result.kind == "answer"
    assert [claim.text for claim in result.claims] == ["Clean."]


def test_refusal_when_every_claim_is_dropped() -> None:
    result = validate_draft(
        DraftAnswer(claims=[Claim(text="Invented.", passage_ids=["nope"])]),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "citations_dropped"


def test_refusal_when_the_drafter_marks_insufficient_evidence() -> None:
    result = validate_draft(
        DraftAnswer(claims=[], insufficient_evidence=True),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"


def test_ambiguous_turn_cites_every_retrieved_passage() -> None:
    result = validate_draft(
        DraftAnswer(
            kind="ambiguous",
            question="Which season or effective date applies?",
            passage_ids=["p1", "p2"],
            claims=[Claim(text="The 2023-24 passage controls.", passage_ids=["p1"])],
        ),
        [_passage("p1"), _passage("p2")],
    )
    assert result.kind == "ambiguous"
    assert result.question == "Which season or effective date applies?"
    assert result.passage_ids == ["p1", "p2"]
    assert set(result.model_dump()) == {"kind", "question", "passage_ids"}


def test_ambiguous_turn_with_an_unretrieved_passage_is_refused() -> None:
    result = validate_draft(
        DraftAnswer(
            kind="ambiguous",
            question="Which season applies?",
            passage_ids=["p1", "missing"],
        ),
        [_passage("p1"), _passage("p2")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"


def test_ambiguous_text_after_the_question_is_refused() -> None:
    result = validate_draft(
        DraftAnswer(
            kind="ambiguous",
            question="Which season applies? Section 2 controls",
            passage_ids=["p1", "p2"],
        ),
        [_passage("p1"), _passage("p2")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"


def test_ambiguous_statement_that_could_pick_a_passage_is_refused() -> None:
    result = validate_draft(
        DraftAnswer(
            kind="ambiguous",
            question="Section 2 controls. Which season applies?",
            passage_ids=["p1", "p2"],
        ),
        [_passage("p1"), _passage("p2")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"


def test_missing_inputs_keeps_a_number_that_is_already_in_the_quote() -> None:
    passage = _passage("p1")
    passage = passage.model_copy(
        update={"text": "The maximum is 175 percent of the prior regular salary."}
    )
    result = validate_draft(
        DraftAnswer(
            kind="missing_inputs",
            text="The passage states 175 percent, and the prior regular salary is missing.",
            passage_ids=["p1"],
        ),
        [passage],
    )
    assert result.kind == "missing_inputs"
    assert result.passage_ids == ["p1"]
    assert "175" in result.text
    assert "prior regular salary" in result.text


def test_missing_inputs_with_a_computed_number_is_refused() -> None:
    passage = _passage("p1")
    passage = passage.model_copy(
        update={"text": "The maximum is 175 percent of the prior regular salary."}
    )
    result = validate_draft(
        DraftAnswer(
            kind="missing_inputs",
            text="The prior regular salary is missing, so the result is 2100000.",
            passage_ids=["p1"],
        ),
        [passage],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"
    assert "2100000" not in result.message
