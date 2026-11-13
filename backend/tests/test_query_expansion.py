import re

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.phrases import phrase_ranks, phrase_score, query_phrases
from app.retrieval.text import tokens


def _chunk(section: str, text: str, *, article_title: str = "Exceptions") -> Chunk:
    return Chunk(
        id=section,
        document_id="doc",
        chunk_index=1,
        article_number=7,
        article_title=article_title,
        section=section,
        page_start=1,
        page_end=1,
        text=text,
        source_url="https://example.test",
    )


def test_non_taxpayer_does_not_expand_taxpayer_alias() -> None:
    expanded = expand_query(
        "How large is the Non-Taxpayer Mid-Level Salary Exception in the first salary cap year?"
    ).lower()
    assert "non-taxpayer mid-level salary exception" in expanded
    assert re.search(r"(?<![a-z0-9-])taxpayer mid-level salary exception", expanded) is None


def test_cap_alias_skips_salary_cap_but_expands_bare_cap() -> None:
    with_salary_cap = expand_query(
        "How large is the Non-Taxpayer Mid-Level Salary Exception in the first salary cap year?"
    ).lower()
    assert "salary cap team salary" not in with_salary_cap
    bare = expand_query("What counts toward the cap vs. what doesn't.").lower()
    assert "salary cap team salary" in bare


def test_taxpayer_alias_still_expands_on_its_own() -> None:
    expanded = expand_query("How large is the taxpayer mid-level exception?").lower()
    assert "taxpayer mid-level salary exception" in expanded
    assert "non-taxpayer mid-level salary exception" not in expanded


def test_tokens_ignore_stopwords() -> None:
    assert "the" not in tokens("the salary cap")
    assert "salary" in tokens("the salary cap")


def test_query_phrases_keep_long_titles_and_hyphenated_bigrams() -> None:
    phrases = query_phrases(
        "What first-year salary can a Qualifying Veteran Free Agent's new contract reach?"
    )
    assert "qualifying veteran free agent" in phrases
    apron = query_phrases("What is Apron Team Salary, relative to Team Salary?")
    assert "apron team salary" in apron
    assert "team salary" not in apron
    two_way = query_phrases("How is the salary in a Two-Way contract set?")
    assert "two-way contract" in two_way


def test_phrase_boundary_does_not_treat_non_qualifying_as_qualifying() -> None:
    question = "What first-year salary can a Qualifying Veteran Free Agent's new contract reach?"
    phrases = query_phrases(question)
    qualifying = _chunk(
        "6(b)(1) If the player is a Qualifying Veteran Free Agent",
        "The first-year salary may reach the maximum.",
    )
    non_qualifying = _chunk(
        "6(b)(2) If the player is a Non-Qualifying Veteran Free Agent",
        "The first-year salary is limited.",
    )
    assert phrase_score(qualifying, phrases) > phrase_score(non_qualifying, phrases)
    ranked = phrase_ranks(question, [non_qualifying, qualifying])
    assert ranked[0] == qualifying.id
