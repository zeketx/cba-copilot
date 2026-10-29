from pathlib import Path

from ingest.chunker import article_number_from_aid_name, chunk_markdown, roman_to_int

FIXTURE = Path(__file__).parent / "fixtures" / "article_vii_excerpt.md"
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


def test_roman_and_aid_filename() -> None:
    assert roman_to_int("XXIX") == 29
    assert roman_to_int("VII") == 7
    assert article_number_from_aid_name("07-BASKETBALL.Rmd") == 7
    assert article_number_from_aid_name("docs/11-FREE-AGENCY.md") == 11
    assert article_number_from_aid_name("README.md") is None
