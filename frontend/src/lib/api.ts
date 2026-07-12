// Thin fetch wrappers around the backend control endpoints in server.py.
//
// All run-control calls share the same shape, so a single helper keeps error
// handling consistent. An optional API token (for token-protected deploys) is
// read from localStorage and sent as `x-api-key`.

const TOKEN_KEY = "verity_api_token";

export function getApiToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore storage failures (private mode, etc.) */
  }
}

/** Build the SSE URL, including the token as a query param when set. */
export function buildRunUrl(url: string, instructions: string): string {
  const params = new URLSearchParams({ url, instructions });
  return `/api/run?${params.toString()}`;
}

async function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  const token = getApiToken();
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "x-api-key": token } : {}),
    },
    body: body ? JSON.stringify(body) : "{}",
  });

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const parsed = await res.json();
      detail = parsed.detail || JSON.stringify(parsed);
    } catch {
      /* fall back to status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export interface HeadlessResult {
  ok: boolean;
  headless_before: boolean;
  headless_after: boolean;
}

export const api = {
  cancel: (runId: string) => post(`/api/runs/${encodeURIComponent(runId)}/cancel`),

  respond: (runId: string, answer: string) =>
    post(`/api/runs/${encodeURIComponent(runId)}/respond`, { answer }),

  setHeadless: (runId: string, headless: boolean) =>
    post<HeadlessResult>(`/api/runs/${encodeURIComponent(runId)}/headless`, { headless }),

  captchaStart: (runId: string) =>
    post<HeadlessResult>(`/api/runs/${encodeURIComponent(runId)}/captcha/start`),

  captchaSolved: (runId: string) =>
    post<HeadlessResult>(`/api/runs/${encodeURIComponent(runId)}/captcha/solved`),
};
