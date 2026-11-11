from ingest.cba_text import chunk_cba_text

SOURCE = "https://example.test/cba.pdf"

LAYOUT = """
                                                              Article I      1

                               ARTICLE I

                             DEFINITIONS

Section 1.    Definitions.
   (t)     "Early Qualifying Veteran Free Agent" means two seasons.
(2) Salary Cap Years) multiplied by thirteen.
   (yy)     "Qualifying Veteran Free Agent" means three seasons.
(3) Seasons.

                               ARTICLE VII

          BASKETBALL RELATED INCOME

Section 2.    Salary Cap, Minimum Team Salary, Tax Level, Apron
              Levels, and Draft Pick Penalty.
  (h) Hotel arrangements stay in this section.
  (i) Minimum Player Salary Exception. A Team may sign a player.
Section 11.

  (j) Two-Way Contracts. Two-Way Player Salaries shall be excluded.

Section 6.   Exceptions to the Salary Cap.
   (a) Existing Contracts. A Team may exceed the Salary Cap.
      (1) For each Salary Cap Year the numbered child applies.
          (i) Standard child under a number.
  (e) (1) Subject to the rules, a Veteran Free Agent may sign and then trade.
(A)    A Team may not engage in a transaction set forth in row A.

EXHIBIT A
UNIFORM PLAYER CONTRACT
"""


def _chunks(text: str = LAYOUT, page_offset: int = 0):
    return chunk_cba_text(text, source_url=SOURCE, page_offset=page_offset)


def test_definition_markers_ignore_wrapped_parentheticals() -> None:
    chunks = _chunks()
    early = next(chunk for chunk in chunks if chunk.section.startswith("1(t)"))
    bird = next(chunk for chunk in chunks if chunk.section.startswith("1(yy)"))
    assert "Salary Cap Years" in early.text
    assert "three seasons" in bird.text
    assert "Seasons." in bird.text
    assert not any("(3)" in chunk.section for chunk in chunks if chunk.article_number == 1)


def test_letter_i_after_h_is_a_sibling_and_a_bare_section_line_is_not() -> None:
    chunks = _chunks()
    labels = [chunk.section for chunk in chunks if chunk.article_number == 7]
    assert any(label.startswith("2(i)") for label in labels)
    assert not any(label.startswith("2(h)(i)") for label in labels)
    two_way = next(chunk for chunk in chunks if "Two-Way Player Salaries" in chunk.text)
    assert two_way.section.startswith("2(j)")
    assert two_way.article_number == 7


def test_numbered_child_then_roman_and_sign_and_trade_marker() -> None:
    chunks = _chunks()
    roman = next(chunk for chunk in chunks if "Standard child under a number" in chunk.text)
    assert roman.section.startswith("6(a)(1)(i)")
    trade = next(chunk for chunk in chunks if "sign and then trade" in chunk.text)
    assert trade.section.startswith("6(e)")
    assert "row A" in trade.text
    assert not any(chunk.section.startswith("6(a) ") and "row A" in chunk.text for chunk in chunks)


def test_wrapped_section_title_and_exhibit() -> None:
    chunks = _chunks()
    apron = next(chunk for chunk in chunks if chunk.section.startswith("2 "))
    assert "Draft Pick Penalty" in apron.section
    exhibit = next(chunk for chunk in chunks if chunk.article_number is None)
    assert exhibit.section == "Exhibit A"
    assert "UNIFORM PLAYER CONTRACT" in exhibit.text


def test_page_offset_uses_the_viewer_page_in_the_url() -> None:
    text = "ARTICLE II\n\nCONTRACT\n\nSection 1. Required.\nAlpha.\n\f\n2 Article II\n\nBeta.\n"
    chunks = chunk_cba_text(text, source_url=SOURCE, page_offset=0)
    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert chunks[0].source_url == f"{SOURCE}#page=1"
    assert "Beta" in chunks[0].text
    assert "2 Article II" not in chunks[0].text
