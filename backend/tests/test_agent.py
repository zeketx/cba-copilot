import pytest
from app.assistant.drafter import (
    DEFAULT_ANSWER_MAX_TOKENS,
    AgentDrafter,
    build_agent,
    build_live_model,
    format_passages,
)
from app.config import Settings
from app.demo import demo_embedder, demo_store, load_demo_chunks
from app.domain import DraftAnswer
from app.pipeline import answer_question
from app.retrieval.embed import OpenAIEmbedder
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel


def test_stand_in_model_answer_keeps_a_retrieved_citation() -> None:
    passage = load_demo_chunks()[0]
    quote = " ".join(passage.text.split())[:80]
    agent = build_agent(
        TestModel(
            custom_output_args={
                "status": "answer",
                "claims": [
                    {
                        "text": "Cited from the passage.",
                        "quote": quote,
                        "passage_ids": [passage.id],
                    }
                ],
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


def test_stand_in_model_quote_missing_from_passage_is_dropped() -> None:
    passage = load_demo_chunks()[0]
    agent = build_agent(
        TestModel(
            custom_output_args={
                "status": "answer",
                "claims": [
                    {
                        "text": "A number the passage never states.",
                        "quote": "this span is not in the retrieved passage",
                        "passage_ids": [passage.id],
                    }
                ],
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


def test_stand_in_model_unknown_citation_becomes_a_refusal() -> None:
    agent = build_agent(
        TestModel(
            custom_output_args={
                "status": "answer",
                "claims": [
                    {
                        "text": "Not in the set.",
                        "quote": "Not in the set.",
                        "passage_ids": ["not-retrieved"],
                    }
                ],
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


def test_live_embedder_refuses_before_a_call() -> None:
    try:
        OpenAIEmbedder(Settings()).embed_query("aprons")
    except RuntimeError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("embedding guard did not raise")


def test_stand_in_model_ambiguous_draft_is_a_clarification() -> None:
    chunks = load_demo_chunks()
    by_id = {chunk.id: chunk for chunk in chunks}
    bird = by_id["bird"]
    early = by_id["early-bird"]
    agent = build_agent(
        TestModel(
            custom_output_args={
                "status": "ambiguous",
                "claims": [
                    {
                        "text": bird.text.strip(),
                        "quote": bird.text.strip(),
                        "passage_ids": [bird.id],
                    },
                    {
                        "text": early.text.strip(),
                        "quote": early.text.strip(),
                        "passage_ids": [early.id],
                    },
                ],
            }
        )
    )
    response = answer_question(
        "Bird vs. Early Bird rights in plain English.",
        demo_store(),
        demo_embedder(),
        AgentDrafter(agent),
    )
    assert response.kind == "clarification"
    assert response.reason == "ambiguous"
    cited = {passage_id for claim in response.claims for passage_id in claim.passage_ids}
    assert cited == {bird.id, early.id}


def test_agent_output_type_is_the_draft() -> None:
    agent = build_agent(TestModel())
    assert agent.output_type is DraftAnswer


@pytest.mark.parametrize(
    ("provider", "model", "key_field", "expected_name"),
    [
        ("openai", "", "openai_api_key", "gpt-4o"),
        ("google", "gemini-2.5-flash", "gemini_api_key", "gemini-2.5-flash"),
        ("openrouter", "openai/gpt-4o", "openrouter_api_key", "openai/gpt-4o"),
    ],
)
def test_live_model_takes_its_key_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    model: str,
    key_field: str,
    expected_name: str,
) -> None:
    for name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(
        _env_file=None,
        answer_provider=provider,
        answer_model=model,
        **{key_field: "test-key"},
    )
    built = build_live_model(settings)
    assert built.model_name == expected_name


def test_answer_model_runs_with_budget_settings() -> None:
    seen: list[object] = []

    def respond(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(info.model_settings)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"status": "insufficient_evidence", "claims": []},
                )
            ]
        )

    draft = AgentDrafter(build_agent(FunctionModel(respond))).draft("q", [])
    assert draft.status == "insufficient_evidence"
    assert seen == [
        {"temperature": 0, "timeout": 60, "max_tokens": DEFAULT_ANSWER_MAX_TOKENS}
    ]


def test_format_passages_clips_a_huge_chunk_and_keeps_the_id() -> None:
    passage = load_demo_chunks()[0]
    huge = passage.model_copy(update={"text": "salary " * 20_000})
    prompt = format_passages("What is the cap?", [huge])
    assert f"[{huge.id}]" in prompt
    assert len(prompt) < 10_000
    assert prompt.count("[") == 1
