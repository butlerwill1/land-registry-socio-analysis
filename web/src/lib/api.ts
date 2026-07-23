import type { PlanId } from "./plans";

let accessToken: string | undefined;

export function setApiAccessToken(token: string | undefined): void {
  accessToken = token;
}

export function buildApiHeaders(
  plan: PlanId,
  contentType?: "json",
): Record<string, string> {
  const headers: Record<string, string> = {};
  if (contentType === "json") headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (import.meta.env.DEV) {
    headers["X-Dev-Plan"] = plan;
    headers["X-Dev-User"] = "local-preview";
  }
  return headers;
}

export async function fetchApi<T>(
  path: string,
  plan: PlanId,
  init: RequestInit = {},
  request: typeof fetch = fetch,
): Promise<T> {
  const response = await request(path, {
    ...init,
    credentials: "include",
    headers: {
      ...buildApiHeaders(plan),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let message = `The API request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      // Keep the status-based error when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
