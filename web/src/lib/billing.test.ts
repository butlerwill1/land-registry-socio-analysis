import { describe, expect, it, vi } from "vitest";
import { createCheckout, createCustomerPortal } from "./billing";

describe("billing API client", () => {
  it("creates a Pro Checkout Session with the selected interval", async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ url: "https://checkout.stripe.test/session" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(createCheckout("year", request)).resolves.toBe(
      "https://checkout.stripe.test/session",
    );
    expect(request).toHaveBeenCalledWith("/api/billing/checkout", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Dev-Plan": "free",
        "X-Dev-User": "local-preview",
      },
      body: JSON.stringify({ plan: "pro", interval: "year" }),
    });
  });

  it("surfaces a billing service error", async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Billing is disabled." }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(createCheckout("month", request)).rejects.toThrow("Billing is disabled.");
  });

  it("rejects a malformed successful response", async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(createCheckout("month", request)).rejects.toThrow("invalid Checkout URL");
  });

  it("creates a Customer Portal link", async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ url: "https://billing.stripe.test/portal" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(createCustomerPortal(request)).resolves.toBe(
      "https://billing.stripe.test/portal",
    );
    expect(request).toHaveBeenCalledWith("/api/billing/portal", {
      method: "POST",
      credentials: "include",
      headers: {
        "X-Dev-Plan": "pro",
        "X-Dev-User": "local-preview",
      },
    });
  });
});
