import { Check, LockKeyhole, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createCheckout } from "../lib/billing";
import {
  formatPlanPrice,
  monthlyEquivalent,
  productPlans,
  type BillingInterval,
  type PlanId,
} from "../lib/plans";

interface PricingDialogProps {
  open: boolean;
  currentPlan: PlanId;
  allowLocalPreview?: boolean;
  onClose: () => void;
  onPreviewPro: () => void;
}

export function PricingDialog({
  open,
  currentPlan,
  allowLocalPreview = false,
  onClose,
  onPreviewPro,
}: PricingDialogProps) {
  const [interval, setInterval] = useState<BillingInterval>("month");
  const [checkoutPending, setCheckoutPending] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string>();

  useEffect(() => {
    if (!open) {
      setCheckoutPending(false);
      setCheckoutError(undefined);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  const startCheckout = async () => {
    setCheckoutPending(true);
    setCheckoutError(undefined);
    try {
      window.location.assign(await createCheckout(interval));
    } catch (reason) {
      setCheckoutError(
        reason instanceof Error ? reason.message : "Stripe Checkout could not be started.",
      );
      setCheckoutPending(false);
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="pricing-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pricing-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="pricing-header">
          <div>
            <h2 id="pricing-title">Choose your level of detail</h2>
            <p>Start with London market data for free. Upgrade when deeper local analysis matters.</p>
          </div>
          <button type="button" className="icon-button" aria-label="Close pricing" onClick={onClose}>
            <X size={19} />
          </button>
        </header>

        <div className="billing-toggle" role="group" aria-label="Billing interval">
          <button
            type="button"
            className={interval === "month" ? "active" : ""}
            aria-pressed={interval === "month"}
            onClick={() => setInterval("month")}
          >
            Monthly
          </button>
          <button
            type="button"
            className={interval === "year" ? "active" : ""}
            aria-pressed={interval === "year"}
            onClick={() => setInterval("year")}
          >
            Annual
            <span>Save 20%</span>
          </button>
        </div>

        <div className="plan-grid">
          {(["free", "pro"] as const).map((planId) => {
            const plan = productPlans[planId];
            const isCurrent = currentPlan === planId;
            return (
              <article className={`plan-card ${planId === "pro" ? "featured" : ""}`} key={planId}>
                <div className="plan-heading">
                  <div>
                    <h3>{plan.name}</h3>
                    <p>{plan.description}</p>
                  </div>
                  {planId === "pro" && <LockKeyhole size={20} aria-hidden="true" />}
                </div>
                <div className="plan-price">
                  <strong>{formatPlanPrice(planId, interval)}</strong>
                  <span>/{interval}</span>
                </div>
                {planId === "pro" && interval === "year" && (
                  <p className="price-equivalent">
                    £{monthlyEquivalent(planId, interval).toFixed(0)} per month, billed annually
                  </p>
                )}
                <ul>
                  {plan.features.map((feature) => (
                    <li key={feature}>
                      <Check size={15} aria-hidden="true" />
                      {feature}
                    </li>
                  ))}
                </ul>
                {planId === "free" ? (
                  <button type="button" className="plan-button secondary" disabled={isCurrent}>
                    {isCurrent ? "Current plan" : "Free plan"}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="plan-button primary"
                    disabled={isCurrent || checkoutPending}
                    onClick={startCheckout}
                  >
                    {isCurrent ? "Current plan" : checkoutPending ? "Opening Checkout..." : "Upgrade to Pro"}
                  </button>
                )}
              </article>
            );
          })}
        </div>

        {checkoutError && (
          <p className="billing-error" role="alert">
            {checkoutError}
          </p>
        )}
        <footer className="pricing-footer">
          <span>Prices are launch hypotheses. VAT may apply.</span>
          {allowLocalPreview && currentPlan === "free" && (
            <button
              type="button"
              className="text-button"
              onClick={() => {
                onPreviewPro();
                onClose();
              }}
            >
              Preview Pro locally
            </button>
          )}
        </footer>
      </section>
    </div>
  );
}
