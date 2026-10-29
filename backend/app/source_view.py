from __future__ import annotations

import html
from typing import Literal

from pydantic import BaseModel

from app.domain import Chunk


class SpanPlacement(BaseModel):
    kind: Literal["span"] = "span"
    start_id: str
    end_id: str


class ElementPlacement(BaseModel):
    kind: Literal["element"] = "element"
    element_id: str


def render_source(cited: Chunk, chunks: list[Chunk]) -> tuple[str, SpanPlacement]:
    start_id = f"cite-start-{cited.id}"
    end_id = f"cite-end-{cited.id}"
    sections: list[str] = ["<article>"]
    for chunk in chunks:
        title = html.escape(f"Article {chunk.article_number}. {chunk.article_title}")
        section = html.escape(chunk.section)
        body = html.escape(chunk.text)
        if chunk.id == cited.id:
            body = (
                f'<span id="{html.escape(start_id)}"></span>'
                f"{body}"
                f'<span id="{html.escape(end_id)}"></span>'
            )
        sections.append(
            "<section>"
            f'<h2 data-filing-heading="true">{title}</h2>'
            f"<h3>{section}</h3>"
            f"<p>{body}</p>"
            "</section>"
        )
    sections.append("</article>")
    return "\n".join(sections), SpanPlacement(start_id=start_id, end_id=end_id)
