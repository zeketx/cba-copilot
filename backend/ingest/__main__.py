from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select

_BACKEND = Path(__file__).resolve().parent.parent
_DEFAULT_PDF = _BACKEND.parent / "data" / "downloads" / "2023-nba-cba.pdf"
_DEFAULT_MANIFEST = _BACKEND.parent / "data" / "downloads" / "manifest.json"
_DEFAULT_CORPUS = _BACKEND.parent / "data" / "corpus.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    load_cmd = sub.add_parser("load")
    load_cmd.add_argument("--dry-run", action="store_true")
    sub.add_parser("embed")
    args = parser.parse_args(argv)
    if args.command == "load":
        return _load(dry_run=args.dry_run)
    return _embed()


def _load(*, dry_run: bool) -> int:
    from ingest.load import upsert_chunks, upsert_document
    from ingest.pdf import measure_offset, read_pages, render_markdown
    from ingest.rows import chunk_rows

    pdf_path = _DEFAULT_PDF
    manifest = json.loads(_DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    corpus = json.loads(_DEFAULT_CORPUS.read_text(encoding="utf-8"))
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise SystemExit("PDF sha256 does not match the manifest")
    pages = read_pages(pdf_path)
    offset = measure_offset(pages)
    expected_offset = int(corpus["pdf_page_offset"])
    if offset != expected_offset:
        raise SystemExit(f"measured offset {offset} does not match corpus {expected_offset}")
    markdown = render_markdown(pages)
    rows = chunk_rows(markdown, source_url=manifest["url"], offset=offset)
    with_refs = sum(1 for row in rows if row.metadata.get("references"))
    articles = sorted({row.article_number for row in rows if row.article_number is not None})
    first = rows[0] if rows else None
    last = rows[-1] if rows else None
    print(f"pages {len(pages)}")
    print(f"offset {offset}")
    print(f"chunks {len(rows)}")
    print(f"chunks with references {with_refs}")
    if articles:
        print(f"articles {articles[0]}-{articles[-1]} ({len(articles)} covered)")
    else:
        print("articles none")
    if first is not None and last is not None:
        print(
            "first "
            f"{first.section} printed={first.printed_page} viewer={first.viewer_page}"
        )
        print(
            "last "
            f"{last.section} printed={last.printed_page} viewer={last.viewer_page}"
        )
    if dry_run:
        return 0
    from app.config import Settings

    settings = Settings()
    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.begin() as conn:
        document_id = upsert_document(
            conn,
            title=str(corpus["title"]),
            source_url=manifest["url"],
            sha256=digest,
            cover_date=manifest["cover_date"],
            printed_term=manifest["printed_term"],
            page_offset=offset,
            effective_start=str(corpus["effective_start"]),
            effective_through=str(corpus["effective_through"]),
            text=markdown,
        )
        upsert_chunks(conn, document_id, rows)
    return 0


def _embed() -> int:
    from app.config import Settings
    from app.database.models import SourceDocument
    from app.retrieval.embed import OpenAIEmbedder

    from ingest.load import embed_missing

    manifest = json.loads(_DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    settings = Settings()
    embedder = OpenAIEmbedder(settings)
    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.connect() as conn:
        document_id = conn.execute(
            select(SourceDocument.id).where(SourceDocument.source_url == manifest["url"])
        ).scalar_one()
    filled = 0
    while True:
        with engine.begin() as conn:
            count = embed_missing(conn, UUID(str(document_id)), embedder)
        if count == 0:
            break
        filled += count
        print(f"filled {filled}")
    print(f"done, filled {filled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
