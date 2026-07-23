import { buildApiHeaders } from "./api";
import type { BillingInterval, PlanId } from "./plans";

interface CheckoutResponse {
  url: string;
}

interface BillingError {
  error?: string;
}

async function readResponseBody(response: Response): Promise<CheckoutResponse | BillingError> {
  try {
    return (await response.json()) as CheckoutResponse | BillingError;
  } catch {
    return {};
  }
}

export async function createCheckout(
  interval: BillingInterval,
  request: typeof fetch = fetch,
  plan: PlanId = "free",
): Promise<string> {
  const response = await request("/api/billing/checkout", {
    method: "POST",
    credentials: "include",
    headers: buildApiHeaders(plan, "json"),
    body: JSON.stringify({ plan: "pro", interval }),
  });
  const body = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(
      "error" in body && body.error
        ? body.error
        : "Stripe Checkout is not configured for this environment.",
    );
  }
  if (!("url" in body) || typeof body.url !== "string" || !body.url) {
    throw new Error("The billing service returned an invalid Checkout URL.");
  }
  return body.url;
}

export async function createCustomerPortal(request: typeof fetch = fetch): Promise<string> {
  const response = await request("/api/billing/portal", {
    method: "POST",
    credentials: "include",
    headers: buildApiHeaders("pro"),
  });
  const body = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(
      "error" in body && body.error
        ? body.error
        : "The subscription portal is not available.",
    );
  }
  if (!("url" in body) || typeof body.url !== "string" || !body.url) {
    throw new Error("The billing service returned an invalid portal URL.");
  }
  return body.url;
}
