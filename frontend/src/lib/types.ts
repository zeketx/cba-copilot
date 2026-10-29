import { readPlacement, type FilingPlacement } from "@/lib/citation";

export type PublicCitation = {
  passageId: string;
  articleNumber: number | null;
  articleTitle: string;
  section: string;
  pageOrSection: string;
  pageStart: number | null;
  pageEnd: number | null;
  sourceUrl: string;
  excerpt: string;
  sourceHtml: string;
  placement: FilingPlacement;
};

export type PublicClaim = {
  text: string;
  citations: PublicCitation[];
};

export type PublicAnswer = {
  kind: "answer";
  claims: PublicClaim[];
};

export type PublicRefusal = {
  kind: "refusal";
  reason: "no_evidence" | "citations_dropped";
  message: string;
};

export type PublicResponse = PublicAnswer | PublicRefusal;

export type ChatTurn = {
  id: string;
  question: string;
  response: PublicResponse;
};

type WireCitation = {
  passage_id: string;
  article_number: number | null;
  article_title: string;
  section: string;
  page_or_section: string;
  page_start: number | null;
  page_end: number | null;
  source_url: string;
  excerpt: string;
  source_html: string;
  placement: unknown;
};

export type WireResponse =
  | {
      kind: "answer";
      claims: { text: string; citations: WireCitation[] }[];
    }
  | {
      kind: "refusal";
      reason: "no_evidence" | "citations_dropped";
      message: string;
    };

function citationFromWire(citation: WireCitation): PublicCitation {
  return {
    passageId: citation.passage_id,
    articleNumber: citation.article_number,
    articleTitle: citation.article_title,
    section: citation.section,
    pageOrSection: citation.page_or_section,
    pageStart: citation.page_start,
    pageEnd: citation.page_end,
    sourceUrl: citation.source_url,
    excerpt: citation.excerpt,
    sourceHtml: citation.source_html,
    placement: readPlacement(citation.placement),
  };
}

export function responseFromWire(body: WireResponse): PublicResponse {
  if (body.kind === "refusal") {
    return body;
  }
  return {
    kind: "answer",
    claims: body.claims.map((claim) => ({
      text: claim.text,
      citations: claim.citations.map(citationFromWire),
    })),
  };
}

export const SAMPLE_QUESTIONS = [
  "What can't a second-apron team do in a trade?",
  "Bird vs. Early Bird rights in plain English.",
  "The 65-game minimum for awards and which awards it covers.",
  "How the taxpayer mid-level exception changes above the second apron.",
  "What counts toward the cap vs. what doesn't.",
  "How many timeouts may an NHL coach call during a playoff overtime?",
];
