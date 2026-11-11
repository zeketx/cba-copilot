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

export type PublicAmbiguous = {
  kind: "ambiguous";
  question: string;
  citations: PublicCitation[];
};

export type PublicMissingInputs = {
  kind: "missing_inputs";
  text: string;
  citations: PublicCitation[];
};

export type PublicResponse = PublicAnswer | PublicRefusal | PublicAmbiguous | PublicMissingInputs;

export type ThreadSummary = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
};

export type UserMessage = {
  id: string;
  role: "user";
  position: number;
  text: string;
};

export type AssistantMessage = {
  id: string;
  role: "assistant";
  position: number;
  response: PublicResponse;
};

export type ChatMessage = UserMessage | AssistantMessage;

export type StreamChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
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
    }
  | {
      kind: "ambiguous";
      question: string;
      citations: WireCitation[];
    }
  | {
      kind: "missing_inputs";
      text: string;
      citations: WireCitation[];
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

export type WireThread = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type WireUserMessage = {
  id: string;
  role: "user";
  position: number;
  text: string;
};

export type WireAssistantMessage = {
  id: string;
  role: "assistant";
  position: number;
  response: WireResponse;
};

export type WireChatMessage = WireUserMessage | WireAssistantMessage;

export function threadFromWire(body: WireThread): ThreadSummary {
  return {
    id: body.id,
    title: body.title,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

export function messageFromWire(body: WireChatMessage): ChatMessage {
  if (body.role === "user") {
    return body;
  }
  return {
    id: body.id,
    role: "assistant",
    position: body.position,
    response: responseFromWire(body.response),
  };
}

export function responseFromWire(body: WireResponse): PublicResponse {
  if (body.kind === "refusal") {
    return body;
  }
  if (body.kind === "ambiguous") {
    return {
      kind: "ambiguous",
      question: body.question,
      citations: body.citations.map(citationFromWire),
    };
  }
  if (body.kind === "missing_inputs") {
    return {
      kind: "missing_inputs",
      text: body.text,
      citations: body.citations.map(citationFromWire),
    };
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
  "What is the biannual exception?",
  "What is the Early Bird maximum in dollars?",
];
