export type FilingPlacement =
  | { kind: "miss" }
  | { kind: "span"; startId: string; endId: string }
  | { kind: "element"; elementId: string };

export function readPlacement(data: unknown): FilingPlacement {
  if (typeof data !== "object" || data === null) {
    return { kind: "miss" };
  }
  const record = data as Record<string, unknown>;
  if (record.kind === "span" && typeof record.start_id === "string" && typeof record.end_id === "string") {
    return { kind: "span", startId: record.start_id, endId: record.end_id };
  }
  if (record.kind === "element" && typeof record.element_id === "string") {
    return { kind: "element", elementId: record.element_id };
  }
  return { kind: "miss" };
}

export function sourceChipLabel(article: number | null, pageOrSection: string): string {
  const articleLabel = article === null ? "CBA" : `Art. ${article}`;
  return [articleLabel, pageOrSection].filter((part) => part !== "").join(" · ");
}

const ROMAN: [number, string][] = [
  [40, "XL"],
  [10, "X"],
  [9, "IX"],
  [5, "V"],
  [4, "IV"],
  [1, "I"],
];

function toRoman(value: number): string {
  let rest = value;
  let out = "";
  for (const [size, numeral] of ROMAN) {
    while (rest >= size) {
      out += numeral;
      rest -= size;
    }
  }
  return out;
}

/** "2. Salary Cap Exceptions / (f)(1)(i) Room" -> "2(f)(1)(i)"; "1(lll) Salary" -> "1(lll)". */
export function sectionCode(section: string): string | null {
  const parts = section.split("/").map((part) => part.trim());
  const numbered = parts.find((part) => /^\d+/.test(part));
  if (numbered === undefined) {
    return null;
  }
  const number = /^\d+[A-Za-z]?/.exec(numbered)?.[0] ?? "";
  const nested = /(?:\([a-z0-9]{1,4}\))+/.exec(parts.slice(parts.indexOf(numbered)).join(" "));
  return `${number}${nested?.[0] ?? ""}`;
}

/** Short inline chip label, e.g. "Art. VII §2(f) p.195" or "Exhibit A §3 p.592". */
export function compactCitationLabel(citation: {
  articleNumber: number | null;
  section: string;
  pageStart: number | null;
}): string {
  const head = citation.section.split("/")[0]?.trim() ?? "";
  const article =
    citation.articleNumber !== null
      ? `Art. ${toRoman(citation.articleNumber)}`
      : /^exhibit\b/i.test(head)
        ? head
        : "CBA";
  const code = sectionCode(citation.section);
  const page = citation.pageStart === null ? null : `p.${citation.pageStart}`;
  return [article, code === null ? null : `§${code}`, page].filter((part) => part !== null).join(" ");
}
