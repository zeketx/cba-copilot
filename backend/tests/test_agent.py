import re

from app.assistant.drafter import (
    CLARIFYING_QUESTION,
    AgentDrafter,
    OverlapDrafter,
    build_agent,
    refuse_live_model,
)
from app.config import Settings
from app.demo import demo_embedder, demo_store, load_demo_chunks
from app.domain import DraftAnswer
from app.pipeline import answer_question
from app.retrieval.embed import OpenAIEmbedder
from pydantic_ai.models.test import TestModel


def test_stand_in_model_answer_keeps_a_retrieved_citation() -> None:
    passage = load_demo_chunks()[0]
    agent = build_agent(
        TestModel(
            custom_output_args={
                "claims": [{"text": "Cited from the passage.", "passage_ids": [passage.id]}],
                "insufficient_evidence": False,
            }
        )
    )
    settings = Settings()
    response = answer_question(
        "What can't a second-apron team do in a trade?",
        demo_store(settings.openai_embedding_dimensions),
        demo_embedder(settings.openai_embedding_dimensions),
        AgentDrafter(agent),
    )
    assert response.kind == "answer"
    assert response.claims[0].passage_ids == [passage.id]


def test_stand_in_model_unknown_citation_becomes_a_refusal() -> None:
    agent = build_agent(
        TestModel(
            custom_output_args={
                "claims": [{"text": "Not in the set.", "passage_ids": ["not-retrieved"]}],
                "insufficient_evidence": False,
            }
        )
    )
    response = answer_question(
        "What can't a second-apron team do in a trade?",
        demo_store(),
        demo_embedder(),
        AgentDrafter(agent),
    )
    assert response.kind == "refusal"
    assert response.reason == "citations_dropped"


def test_live_clients_refuse_before_a_call() -> None:
    try:
        refuse_live_model("gpt-4o")
    except RuntimeError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("live model guard did not raise")
    try:
        OpenAIEmbedder(Settings()).embed_query("aprons")
    except RuntimeError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("embedding guard did not raise")


def test_agent_output_type_is_the_draft() -> None:
    agent = build_agent(TestModel())
    assert agent.output_type is DraftAnswer
    assert set(DraftAnswer.model_fields["kind"].annotation.__args__) == {
        "ambiguous",
        "claims",
        "missing_inputs",
    }


def test_stand_in_model_ambiguous_turn_cites_both_passages() -> None:
    by_id = {chunk.id: chunk for chunk in load_demo_chunks()}
    agent = build_agent(
        TestModel(
            custom_output_args={
                "kind": "ambiguous",
                "question": CLARIFYING_QUESTION,
                "passage_ids": ["biannual-2023", "biannual-2024"],
            }
        )
    )
    response = answer_question(
        "What is the biannual exception?",
        demo_store(),
        demo_embedder(),
        AgentDrafter(agent),
    )
    assert response.kind == "ambiguous"
    assert response.question == CLARIFYING_QUESTION
    assert response.passage_ids == ["biannual-2023", "biannual-2024"]
    assert by_id["biannual-2023"].text != by_id["biannual-2024"].text


def test_stand_in_model_missing_inputs_has_no_computed_number() -> None:
    agent = build_agent(
        TestModel(
            custom_output_args={
                "kind": "missing_inputs",
                "text": "The prior regular salary is missing, so there is no computed number.",
                "passage_ids": ["early-bird"],
            }
        )
    )
    response = answer_question(
        "What is the Early Bird maximum in dollars?",
        demo_store(),
        demo_embedder(),
        AgentDrafter(agent),
    )
    assert response.kind == "missing_inputs"
    assert response.passage_ids == ["early-bird"]
    assert "prior regular salary" in response.text
    assert re.search(r"\d", response.text) is None


def test_overlap_drafter_asks_which_season_when_the_question_names_neither() -> None:
    response = answer_question(
        "What is the biannual exception?",
        demo_store(),
        demo_embedder(),
        OverlapDrafter(),
    )
    assert response.kind == "ambiguous"
    assert response.question == CLARIFYING_QUESTION
    assert response.passage_ids == ["biannual-2023", "biannual-2024"]


def test_overlap_drafter_names_the_passage_when_the_question_names_the_season() -> None:
    response = answer_question(
        "What is the biannual exception for the 2023-24 season?",
        demo_store(),
        demo_embedder(),
        OverlapDrafter(),
    )
    assert response.kind == "answer"
    assert [claim.passage_ids for claim in response.claims] == [["biannual-2023"]]


def test_overlap_drafter_names_a_missing_input_and_does_not_compute() -> None:
    response = answer_question(
        "What is the Early Bird maximum in dollars?",
        demo_store(),
        demo_embedder(),
        OverlapDrafter(),
    )
    assert response.kind == "missing_inputs"
    assert response.passage_ids == ["early-bird"]
    assert "prior regular salary" in response.text
    assert re.search(r"\d", response.text) is None
