export const PDF_IFRAME_SANDBOX = "allow-scripts";
export const FILING_IFRAME_SANDBOX = "";
export const OFFICIAL_PDF_ORIGIN = "https://imgix.cosmicjs.com";

export function officialPdfOrigin(): string {
  return OFFICIAL_PDF_ORIGIN;
}

export function allowedSourceUrl(raw: string): string | null {
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:") {
      return null;
    }
    if (url.origin !== OFFICIAL_PDF_ORIGIN) {
      return null;
    }
    return raw;
  } catch {
    return null;
  }
}
