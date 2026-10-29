from app.assistant.drafter import AgentDrafter, build_agent, refuse_live_model
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
