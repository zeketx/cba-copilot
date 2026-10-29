import { parse } from "yaml";
import corpus from "../../../data/corpus.json";
import rawDefinitions from "../../../definitions/definitions.yaml?raw";

export type DefinitionEntry = {
  term: string;
  definition: string;
  citation: {
    article: number;
    article_title: string;
    section: string;
    page_start: number;
    page_end: number;
    verified: boolean;
  };
};

type DefinitionFile = {
  status: string;
  entries: DefinitionEntry[];
};

export function loadDefinitions(): DefinitionFile {
  return parse(rawDefinitions) as DefinitionFile;
}

export function pdfPageUrl(printedPage: number): string {
  return `${corpus.pdf_url}#page=${printedPage + corpus.pdf_page_offset}`;
}

export function citationLabel(article: number, section: string, pageStart: number, pageEnd: number): string {
  const pages = pageStart === pageEnd ? `p. ${pageStart}` : `pp. ${pageStart}-${pageEnd}`;
  return `Art. ${article} § ${section}, ${pages}`;
}
