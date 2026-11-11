from pathlib import Path

from evals.metrics import section_for_match, section_matches
from ingest.chunker import article_number_from_aid_name, chunk_markdown, roman_to_int

FIXTURE = Path(__file__).parent / "fixtures" / "article_vii_excerpt.md"
DEFINITIONS = Path(__file__).parent / "fixtures" / "article_i_definitions.md"
SOURCE = "https://example.test/cba.pdf"


def _chunks(**kwargs):
    text = FIXTURE.read_text(encoding="utf-8")
    return chunk_markdown(text, source_url=SOURCE, **kwargs)


def test_page_marker_does_not_split_a_section() -> None:
    chunks = _chunks()
    apron = next(chunk for chunk in chunks if "aggregate salaries" in chunk.text)
    assert "Cash in a trade is also restricted" in apron.text
    assert apron.page_start == 210
    assert apron.page_end == 215
    assert apron.source_url == f"{SOURCE}#page=210"
    assert apron.article_number == 7
    assert apron.section.startswith("2(e)")
    assert all("<!--" not in chunk.text for chunk in chunks)


def test_sections_stay_apart() -> None:
    chunks = _chunks()
    assert len(chunks) == 2
    taxpayer = next(chunk for chunk in chunks if "Taxpayer" in chunk.section)
    assert "aggregate salaries" not in taxpayer.text
    assert taxpayer.page_start == 261
    assert taxpayer.page_end == 262


def test_long_section_splits_only_on_subsections() -> None:
    chunks = _chunks(max_section_chars=40)
    apron = [chunk for chunk in chunks if "aggregate salaries" in chunk.text]
    assert len(apron) == 1
    taxpayer = [
        chunk
        for chunk in chunks
        if "five million" in chunk.text or "may not use" in chunk.text
    ]
    assert len(taxpayer) == 2
    assert all(chunk.article_number == 7 for chunk in taxpayer)
    assert any("Amount" in chunk.section for chunk in taxpayer)
    assert any("Limit" in chunk.section for chunk in taxpayer)


def test_article_i_definitions_are_one_chunk_each() -> None:
    text = DEFINITIONS.read_text(encoding="utf-8")
    chunks = chunk_markdown(text, source_url=SOURCE)
    by_token = {}
    for token in ("ll", "rr", "yy", "uuu"):
        matched = [
            chunk
            for chunk in chunks
            if section_matches(section_for_match(chunk.section), f"1({token})")
        ]
        assert len(matched) == 1
        by_token[token] = matched[0]
        assert chunk_does_not_match_shorter(matched[0].section, token)
    extension = next(chunk for chunk in chunks if "(z)" in chunk.section)
    assert "Minimum Team Salary" not in extension.text
    assert "Qualifying Veteran Free Agent" not in extension.text
    assert by_token["ll"].page_start == 29
    assert by_token["rr"].page_start == 30
    assert by_token["yy"].page_start == 30
    assert by_token["uuu"].page_start == 35
    assert by_token["uuu"].page_end == 35
    assert "(i) Included amounts" in by_token["uuu"].text
    assert "must stay whole" in by_token["uuu"].text
    assert all(chunk.article_number == 1 for chunk in chunks)
    later = [chunk for chunk in chunks if chunk.article_number != 1]
    assert later == []


def test_long_definition_splits_on_sub_paragraphs_not_mid_sentence() -> None:
    text = DEFINITIONS.read_text(encoding="utf-8")
    chunks = chunk_markdown(text, source_url=SOURCE, max_section_chars=80)
    team = [
        chunk
        for chunk in chunks
        if section_matches(section_for_match(chunk.section), "1(uuu)")
    ]
    assert len(team) >= 2
    whole = "must stay whole even though it runs past the budget without an interior stop."
    holders = [chunk for chunk in team if whole in chunk.text]
    assert len(holders) == 1
    continued = "means the sum\nof salaries that continues on the next line without a period yet."
    assert any(continued in chunk.text for chunk in team)
    assert all("must stay whole" not in chunk.text or whole in chunk.text for chunk in team)


def test_unquoted_subparagraph_stays_inside_the_definition() -> None:
    text = (
        "# Article I. DEFINITIONS\n"
        "## Section 1. Definitions\n"
        "(a) “Alpha” means one.\n"
        "(i) This sub-paragraph stays inside Alpha.\n"
        "(b) “Beta” means two.\n"
    )
    chunks = chunk_markdown(text, source_url=SOURCE)
    alpha = next(chunk for chunk in chunks if "(a)" in chunk.section)
    beta = next(chunk for chunk in chunks if "(b)" in chunk.section)
    assert "stays inside Alpha" in alpha.text
    assert "stays inside Alpha" not in beta.text
    assert not any(chunk.section.startswith("1. Definitions / (i)") for chunk in chunks)


def test_article_i_section_two_is_not_split_as_definitions() -> None:
    text = (
        "# Article I. DEFINITIONS\n"
        "## Section 2. Uniform Player Contract\n"
        "(a) “Contract” means a writing.\n"
        "(b) “Player” means a person.\n"
    )
    chunks = chunk_markdown(text, source_url=SOURCE)
    assert len(chunks) == 1
    assert chunks[0].section == "2. Uniform Player Contract"


def test_other_articles_do_not_split_on_repeated_letters() -> None:
    text = (
        "# Article VII. BASKETBALL RELATED INCOME\n"
        "## Section 2. Salary Cap\n"
        "(a) “Apron” means a line that is long enough to force a split when the budget is tiny.\n"
        "(aa) “Not a definition” stays inside the previous single-letter group.\n"
        "(b) “Second” starts the next single-letter group.\n"
    )
    chunks = chunk_markdown(text, source_url=SOURCE, max_section_chars=40)
    labels = [chunk.section for chunk in chunks]
    assert any(label.startswith("2. Salary Cap / (a)") for label in labels)
    assert any(label.startswith("2. Salary Cap / (b)") for label in labels)
    assert not any("(aa)" in label for label in labels)
    apron = next(chunk for chunk in chunks if "/ (a)" in chunk.section)
    assert "Not a definition" in apron.text


def chunk_does_not_match_shorter(section: str, token: str) -> bool:
    shorter = token[0]
    return not section_matches(section_for_match(section), f"1({shorter})")


def test_roman_and_aid_filename() -> None:
    assert roman_to_int("XXIX") == 29
    assert roman_to_int("VII") == 7
    assert article_number_from_aid_name("07-BASKETBALL.Rmd") == 7
    assert article_number_from_aid_name("docs/11-FREE-AGENCY.md") == 11
    assert article_number_from_aid_name("README.md") is None
