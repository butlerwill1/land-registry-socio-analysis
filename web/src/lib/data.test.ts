import { describe, expect, it, vi } from "vitest";
import { loadDistrictDetail, loadEntitlements, loadLsoaBoundaries, loadMapMetric, redeemProAccessCode } from "./data";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("premium data API client", () => {
  it("requests the current entitlement", async () => {
    const request = vi.fn().mockResolvedValue(
      jsonResponse({ plan: "pro", authenticated: true, features: ["lsoa_detail"] }),
    );
    const originalFetch = globalThis.fetch;
    globalThis.fetch = request;
    try {
      await expect(loadEntitlements("pro")).resolves.toMatchObject({ plan: "pro" });
    } finally {
      globalThis.fetch = originalFetch;
    }
    expect(request.mock.calls[0][0]).toBe("/api/account/entitlements");
  });

  it("encodes a district code and sends an abort signal", async () => {
    const controller = new AbortController();
    const request = vi.fn().mockResolvedValue(jsonResponse({ district: "SW11" }));
    const originalFetch = globalThis.fetch;
    globalThis.fetch = request;
    try {
      await loadDistrictDetail("SW 11", "pro", controller.signal);
    } finally {
      globalThis.fetch = originalFetch;
    }
    expect(request.mock.calls[0][0]).toBe("/api/data/districts/SW%2011");
    expect(request.mock.calls[0][1].signal).toBe(controller.signal);
  });

  it("requests only one map metric and year", async () => {
    const request = vi.fn().mockResolvedValue(
      jsonResponse({ metric: "income", year: 2025, plan: "pro", values: [] }),
    );
    const originalFetch = globalThis.fetch;
    globalThis.fetch = request;
    try {
      await loadMapMetric("income", 2025, "pro");
    } finally {
      globalThis.fetch = originalFetch;
    }
    expect(request.mock.calls[0][0]).toBe("/api/data/map?metric=income&year=2025");
  });

  it("requests LSOAs for one district and metric", async () => {
    const request = vi.fn().mockResolvedValue(
      jsonResponse({ type: "FeatureCollection", features: [] }),
    );
    const originalFetch = globalThis.fetch;
    globalThis.fetch = request;
    try {
      await loadLsoaBoundaries("SW11", "overall", "pro");
    } finally {
      globalThis.fetch = originalFetch;
    }
    expect(request.mock.calls[0][0]).toBe("/api/data/lsoas/SW11?metric=overall");
  });

  it("redeems a shared Pro access code through the API", async () => {
    const request = vi.fn().mockResolvedValue(
      jsonResponse({ plan: "pro", authenticated: false, features: ["lsoa_detail"] }),
    );
    const originalFetch = globalThis.fetch;
    globalThis.fetch = request;
    try {
      await expect(redeemProAccessCode("FRIEND-CODE")).resolves.toMatchObject({ plan: "pro" });
    } finally {
      globalThis.fetch = originalFetch;
    }
    expect(request.mock.calls[0][0]).toBe("/api/account/access-code");
    expect(request.mock.calls[0][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ code: "FRIEND-CODE" }),
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    });
  });
});
