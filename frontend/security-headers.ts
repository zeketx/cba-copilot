type HeaderSources = {
  supabaseUrl?: string;
  apiBase?: string;
  pdfUrl?: string;
};

const HSTS = "max-age=31536000; includeSubDomains";
const REFERRER = "strict-origin-when-cross-origin";

export function originOf(value: string | undefined): string | null {
  if (value === undefined || value.trim() === "") {
    return null;
  }
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}

export function contentSecurityPolicy(sources: HeaderSources): string {
  const supabase = originOf(sources.supabaseUrl);
  const api = originOf(sources.apiBase);
  const pdf = originOf(sources.pdfUrl);
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "style-src-attr 'unsafe-inline'",
    "img-src 'self'",
    "font-src 'self'",
    `connect-src ${listed("'self'", supabase, api)}`,
    `frame-src ${listed("'self'", pdf)}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

export function securityHeaders(sources: HeaderSources): Record<string, string> {
  return {
    "Content-Security-Policy": contentSecurityPolicy(sources),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": REFERRER,
    "Strict-Transport-Security": HSTS,
  };
}

function listed(...items: Array<string | null>): string {
  const seen: string[] = [];
  for (const item of items) {
    if (item !== null && !seen.includes(item)) {
      seen.push(item);
    }
  }
  return seen.length === 0 ? "'none'" : seen.join(" ");
}
