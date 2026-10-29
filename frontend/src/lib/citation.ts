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
