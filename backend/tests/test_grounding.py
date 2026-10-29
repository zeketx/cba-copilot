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
