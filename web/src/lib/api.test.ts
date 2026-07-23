import { afterEach, describe, expect, it, vi } from "vitest";
import { buildApiHeaders, fetchApi, setApiAccessToken } from "./api";

afterEach(() => {
  setApiAccessToken(undefined);
});

describe("API request boundary", () => {
  it("adds development entitlement headers without treating them as production authority", () => {
    expect(buildApiHeaders("pro", "json")).toEqual({
      "Content-Type": "application/json",
      "X-Dev-Plan": "pro",
      "X-Dev-User": "local-preview",
    });
  });

  it("adds an in-memory bearer token when an authentication SDK supplies one", () => {
    setApiAccessToken("signed-token");
    expect(buildApiHeaders("free")).toEqual({
      Authorization: "Bearer signed-token",
      "X-Dev-Plan": "free",
      "X-Dev-User": "local-preview",
    });
  });

  it("returns typed JSON and includes credentials", async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ plan: "free" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(fetchApi<{ plan: string }>("/api/test", "free", {}, request)).resolves.toEqual({
      plan: "free",
    });
    expect(request).toHaveBeenCalledWith("/api/test", {
      credentials: "include",
      headers: {
        "X-Dev-Plan": "free",
        "X-Dev-User": "local-preview",
      },
    });
  });

  it("surfaces a structured backend error", async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Pro required." }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(fetchApi("/api/test", "free", {}, request)).rejects.toThrow("Pro required.");
  });

  it("falls back to an HTTP status error for a non-JSON response", async () => {
    const request = vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 }));
    await expect(fetchApi("/api/test", "free", {}, request)).rejects.toThrow(
      "The API request failed (503).",
    );
  });
});
