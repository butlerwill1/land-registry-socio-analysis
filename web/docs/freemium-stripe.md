# Freemium and Stripe rollout

The current application implements the product boundary and upgrade experience, but it remains a
static local application. The development-only Pro preview is intentionally not an authentication or
payment system.

## Proposed product model

Free:

- all London postcode districts
- median and average flat prices and transaction counts for the latest five complete years
- district-level overall IMD score

Pro launch hypothesis:

- £15 per month or £144 per year
- 2021 LSOA map detail
- all socioeconomic domain layers
- future downloads and saved research

These prices are hypotheses to validate with users, not a final commercial decision.

## Billing API contract

The browser expects authenticated server endpoints:

```text
POST /api/billing/checkout
Body: { "plan": "pro", "interval": "month" | "year" }
Response: { "url": "https://checkout.stripe.com/..." }

POST /api/billing/portal
Response: { "url": "https://billing.stripe.com/..." }
```

The checkout endpoint should create a Stripe Checkout Session in `subscription` mode using a
server-side Price ID. The portal endpoint should create a Stripe Customer Portal Session for the
authenticated user's Stripe customer.

## Production security boundary

Do not treat the React plan state as authority. Before launch:

1. Add authentication and a database record for each user.
2. Create Checkout Sessions only on the server and derive the user from the authenticated session.
3. Process signed Stripe webhooks idempotently.
4. Store the Stripe customer, subscription, price, status and current period end.
5. Derive entitlements on the server from the stored subscription state.
6. Move premium datasets behind authenticated API or signed-object access. Static files under
   `public/data` can be downloaded regardless of UI gates.
7. Use Stripe Customer Portal for payment method changes and cancellation.

Minimum webhook events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Use Stripe test mode and the Stripe CLI for webhook testing before accepting live payments.

## Suggested production stack

Keep React and Vite for the interface. Add a small server application with:

- an authentication provider
- PostgreSQL for users, subscriptions and saved research
- Stripe Billing with Checkout Sessions and Customer Portal
- server-side entitlement checks
- object storage or API responses for premium data

The server can be Python/FastAPI if that better matches the data pipeline. Pydantic models are useful
for API payloads, Stripe webhook projections and entitlement responses.
