// Browser-style URL normalization for the run form.
//
// Accepts what a user would naturally type — `example.com`, `example.com/login`,
// `localhost:3000`, `http://foo` — and returns a fully-qualified http(s) URL, or
// null when the input can't reasonably be a website.

const SCHEME_RE = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//;
const IPV4_RE = /^\d{1,3}(\.\d{1,3}){3}$/;

export function normalizeUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  // Default missing schemes to https, the way browsers do.
  const candidate = SCHEME_RE.test(trimmed)
    ? trimmed
    : `https://${trimmed.replace(/^\/+/, "")}`;

  let url: URL;
  try {
    url = new URL(candidate);
  } catch {
    return null;
  }

  // Only web protocols make sense as test targets.
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;

  const host = url.hostname;
  const looksReachable =
    host === "localhost" ||
    IPV4_RE.test(host) ||
    host.includes(":") || // IPv6
    host.includes("."); // has a TLD-ish dot
  if (!looksReachable) return null;

  return url.href;
}
