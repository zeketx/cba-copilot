from app.domain import AMBIGUOUS_MESSAGE, Chunk, Claim, DraftAnswer
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
                Claim(text="Season A.", passage_ids=["p1"]),
                Claim(text="Season B.", passage_ids=["p2"]),
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
                Claim(text="Kept.", passage_ids=["p1"]),
                Claim(text="Gone.", passage_ids=["missing"]),
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
            claims=[Claim(text="Needs a salary.", passage_ids=["p1"])],
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
            claims=[Claim(text="Needs a salary.", passage_ids=["p1"])],
            missing_inputs=["  ", ""],
        ),
        [_passage("p1")],
    )
    assert result.kind == "refusal"
    assert result.reason == "no_evidence"
