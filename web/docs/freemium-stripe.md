# Freemium and Stripe architecture

The application now has a FastAPI service under `backend`. The development-only Pro
preview exercises server-enforced data endpoints but is intentionally not proof of
payment.

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

## Billing API

The browser uses authenticated server endpoints:

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

React plan state is never treated as authority. The implementation:

1. signs browser users in through OIDC Authorization Code with PKCE
2. verifies production identities with an OIDC bearer token
3. creates or updates a database user from the verified token subject
4. creates Checkout Sessions only on the server
5. processes signed Stripe webhooks idempotently and reconciles current subscription state
6. stores multiple subscriptions per user, including customer, price, status and period end
7. derives entitlements only from eligible configured Stripe Price IDs
8. keeps full history and LSOA data outside `web/public`
9. returns one requested district, map cross-section, or LSOA layer
10. uses Stripe Customer Portal for payment method changes and cancellation

Minimum webhook events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Use Stripe test mode and the Stripe CLI for webhook testing before accepting live payments.

## Production deployment

Use PostgreSQL by setting `ATLAS_DATABASE_URL`, configure all OIDC and Stripe
variables from `backend/.env.example`, disable development entitlements, and run the
provided backend Dockerfile. See `backend/README.md` for local and production
configuration.
