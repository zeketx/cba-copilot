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
    bare = expand_query("What is excluded from the cap?").lower()
    assert "salary cap" in bare
    assert "team salary" not in bare


def test_second_apron_alias_names_the_restrictions_table() -> None:
    expanded = expand_query("What can't a second-apron team do in a trade?").lower()
    assert "transaction restrictions" in expanded
    assert "second apron level" in expanded


def test_salary_definition_alias_does_not_fire_on_apron_team_salary() -> None:
    salary = expand_query(
        "What does Salary mean, and which amounts are included when computing Team Salary?"
    ).lower()
    assert "not including unlikely bonuses" in salary
    apron = expand_query("What does Apron Team Salary mean, relative to Team Salary?").lower()
    assert "not including unlikely bonuses" not in apron


def test_phrase_match_skips_a_parenthetical_restatement() -> None:
    phrases = ["sixty-five regular season games"]
    chunk = _chunk(
        "6(a) Award Eligibility",
        "No player is eligible unless he played in at least sixty-five (65) Regular Season games.",
        article_title="League Honors",
    )
    assert phrase_score(chunk, phrases) > 0


def test_phrase_match_treats_a_newline_as_a_space() -> None:
    question = "What can't a second-apron team do in a trade?"
    phrases = query_phrases(question)
    table = _chunk(
        "2(e)(4) Transaction Restrictions Table",
        "H. Aggregated Standard Traded Player Exception\nSecond Apron\nLevel",
        article_title="Salary Cap",
    )
    assert phrase_score(table, phrases) > 0
    assert any(phrase == "second apron level" for phrase in phrases)


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
    cap = query_phrases("How large is the salary cap this year?")
    assert "salary cap" not in cap
    bonuses = query_phrases("Does Salary include Unlikely Bonuses?")
    assert "unlikely bonuses" in bonuses
    computing = query_phrases(
        "What does Salary mean, and which amounts are included when computing Team Salary?"
    )
    assert "computing team salary" in computing
    assert "including unlikely bonuses" in computing


def test_cap_inclusions_phrases_prefer_definition_and_computation() -> None:
    question = (
        "What does Salary mean, and which amounts are included when computing Team Salary?"
    )
    salary = _chunk(
        '1(lll) “Salary” means, with respect to a Salary Cap Year, a player’s',
        '“Salary” means, with respect to a Salary Cap Year, a player’s Compensation, '
        "not including Unlikely Bonuses.",
        article_title="DEFINITIONS",
    )
    heading = _chunk(
        "4 Determination of Team Salary",
        "Section 4. Determination of Team Salary.",
        article_title="BRI",
    )
    body = _chunk(
        "4(a) Computation",
        "For purposes of computing Team Salary under this Agreement, "
        "all of the following amounts shall be included:",
        article_title="BRI",
    )
    apron = _chunk(
        "2(e)(1) Apron Team Salary",
        "Apron Team Salary means Team Salary plus other amounts.",
        article_title="BRI",
    )
    ranked = phrase_ranks(question, [heading, apron, body, salary])
    assert set(ranked[:2]) == {salary.id, body.id}


def test_phrase_match_folds_a_trailing_s() -> None:
    phrases = ["salary mean"]
    chunk = _chunk(
        '1(lll) “Salary” means',
        "Salary means Compensation for the season.",
        article_title="DEFINITIONS",
    )
    assert phrase_score(chunk, phrases) > 0


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
