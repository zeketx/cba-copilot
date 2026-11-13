import pytest
from ingest.pdf import PdfPage, join_hyphens, measure_offset, render_markdown, split_header
from ingest.rows import chunk_rows


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Taxpayer Mid -Level Salary Exception", "Taxpayer Mid-Level Salary Exception"),
        ("sixty -two games, a season -ending injury", "sixty-two games, a season-ending injury"),
        ("a Two- Way Contract for 2023- 24", "a Two-Way Contract for 2023-24"),
        ("a -b -c", "a-b-c"),
        ("Team- or League-related content", "Team- or League-related content"),
        ("First- through third-highest", "First- through third-highest"),
        ("pre- and post-season", "pre- and post-season"),
        ("(80% - 79%)", "(80% - 79%)"),
    ],
)
def test_join_hyphens(raw: str, expected: str) -> None:
    assert join_hyphens(raw) == expected

ODD = (
    "  Article I 1 \nARTICLE I\n\nDEFINITIONS\n"
    "Section 1. Definitions.\nThe term Player means a player.\n"
)
EVEN = "2 Article I \nA contract is a writing.\n"
TOC_ODD = "  Table of Contents i \nArticle I .............. 1\n"
TOC_EVEN = "ii Table of Contents \nARTICLE III PLAYER EXPENSES\n"
EXHIBIT_ODD = "  Exhibit A A-1 \nEXHIBIT A\nUniform Player Contract\n"
EXHIBIT_EVEN = "A-2 Exhibit A \n3. COMPENSATION.\nThe Team agrees to pay the Player.\n"
EXHIBIT_J = "Exhibit J-2 J-2-7 \nRelated Party Transactions\n"


def test_split_header_odd_even_toc_and_exhibit() -> None:
    odd = split_header(25, ODD)
    assert odd == PdfPage(
        viewer=25,
        printed="1",
        body="ARTICLE I\n\nDEFINITIONS\nSection 1. Definitions.\nThe term Player means a player.",
    )
    even = split_header(26, EVEN)
    assert even.printed == "2"
    assert even.body.startswith("A contract is a writing.")
    toc = split_header(1, TOC_ODD)
    assert toc.printed is None
    assert "Article I" in toc.body
    toc_even = split_header(2, TOC_EVEN)
    assert toc_even.printed is None
    exhibit = split_header(585, EXHIBIT_ODD)
    assert exhibit.printed == "A-1"
    exhibit_even = split_header(586, EXHIBIT_EVEN)
    assert exhibit_even.printed == "A-2"
    exhibit_j = split_header(676, EXHIBIT_J)
    assert exhibit_j.printed == "J-2-7"


def test_measure_offset_equal_and_disagreeing() -> None:
    pages = [
        split_header(1, TOC_ODD),
        split_header(25, ODD),
        split_header(26, EVEN),
        split_header(201, "  Article VII 177 \nbody\n"),
    ]
    assert measure_offset(pages) == 24
    broken = pages + [split_header(27, "10 Article I \nnope\n")]
    with pytest.raises(ValueError, match="27"):
        measure_offset(broken)
    with pytest.raises(ValueError, match="no Article header"):
        measure_offset([split_header(1, TOC_ODD), split_header(585, EXHIBIT_ODD)])


def test_render_markdown_rewrites_headings_and_keeps_exhibits() -> None:
    pages = [
        split_header(1, TOC_ODD),
        split_header(25, ODD),
        split_header(26, EVEN),
        split_header(585, EXHIBIT_ODD),
        split_header(586, EXHIBIT_EVEN),
    ]
    markdown = render_markdown(pages)
    assert "<!-- pdf-page: 25 printed: 1 -->" in markdown
    assert "<!-- pdf-page: 26 printed: 2 -->" in markdown
    assert "# Article I. DEFINITIONS" in markdown
    assert "## Section 1. Definitions" in markdown
    assert "ARTICLE I" not in markdown
    assert "Table of Contents" not in markdown
    assert "<!-- pdf-page: 585 printed: A-1 -->" in markdown
    assert "<!-- pdf-page: 586 printed: A-2 -->" in markdown
    assert "# Exhibit A. Uniform Player Contract" in markdown
    assert "## 3. Compensation" in markdown
    rows = chunk_rows(markdown, source_url="https://example.test/cba.pdf", offset=24)
    article_rows = [row for row in rows if row.article_number == 1]
    exhibit_rows = [row for row in rows if row.article_number is None]
    assert len(article_rows) == 1
    row = article_rows[0]
    assert "The term Player means a player." in row.text
    assert "A contract is a writing." in row.text
    assert row.page_start == 1
    assert row.page_end == 2
    assert row.printed_page == 1
    assert row.viewer_page == 25
    assert row.source_url.endswith("#page=25")
    assert "Article I 1" not in row.text
    assert "2 Article I" not in row.text
    assert exhibit_rows
    exhibit = exhibit_rows[-1]
    assert exhibit.article_title.startswith("Exhibit A")
    assert "Exhibit A / 3. Compensation" in exhibit.section or exhibit.section.endswith(
        "3. Compensation"
    )
    assert "3. COMPENSATION" in exhibit.text or "3. Compensation" in exhibit.text
    assert exhibit.printed_page is None
    assert exhibit.page_start is None
    assert exhibit.viewer_page == 586
    assert exhibit.source_url.endswith("#page=586")
    assert exhibit.metadata["printed_label"] == "A-2"


def test_a_wrapped_cross_reference_does_not_open_a_section() -> None:
    page = split_header(
        25,
        "  Article I 1 \nARTICLE I\nDEFINITIONS\n"
        "Section 1. Definitions.\nThe rules described in Article VII,\n"
        "Section 12. If in connection with such disputes, this Section applies.\n"
        "Section 2. Uniform Player Contract.\nA contract is a writing.\n",
    )
    markdown = render_markdown([page])
    assert "## Section 12." not in markdown
    rows = chunk_rows(markdown, source_url="https://example.test/cba.pdf", offset=24)
    assert [row.section for row in rows] == ["1. Definitions", "2. Uniform Player Contract"]
    assert "Section 12. If in connection" in rows[0].text
