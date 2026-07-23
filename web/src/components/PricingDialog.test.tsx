import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PricingDialog } from "./PricingDialog";

function renderDialog(overrides: Partial<React.ComponentProps<typeof PricingDialog>> = {}) {
  const props: React.ComponentProps<typeof PricingDialog> = {
    open: true,
    currentPlan: "free",
    authenticated: true,
    authConfigured: false,
    allowLocalPreview: true,
    onClose: vi.fn(),
    onPreviewPro: vi.fn(),
    onSignIn: vi.fn(),
    ...overrides,
  };
  render(<PricingDialog {...props} />);
  return props;
}

describe("PricingDialog", () => {
  it("does not render while closed", () => {
    renderDialog({ open: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the monthly Free and Pro offers", () => {
    renderDialog();
    expect(screen.getByRole("heading", { name: "Free" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeVisible();
    expect(screen.getByText("£15")).toBeVisible();
    expect(screen.getByText("5 years of prices and transactions")).toBeVisible();
    expect(screen.getByText("2021 LSOA-level map detail")).toBeVisible();
  });

  it("switches to annual pricing and shows the monthly equivalent", async () => {
    renderDialog();
    await userEvent.click(screen.getByRole("button", { name: /Annual/ }));
    expect(screen.getByText("£144")).toBeVisible();
    expect(screen.getByText("£12 per month, billed annually")).toBeVisible();
  });

  it("closes with the close button", async () => {
    const props = renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "Close pricing" }));
    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("enables the local Pro preview and closes the dialog", async () => {
    const props = renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "Preview Pro locally" }));
    expect(props.onPreviewPro).toHaveBeenCalledOnce();
    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("does not expose the local preview in a production-like state", () => {
    renderDialog({ allowLocalPreview: false });
    expect(screen.queryByRole("button", { name: "Preview Pro locally" })).not.toBeInTheDocument();
  });

  it("starts sign-in before checkout for an anonymous production user", async () => {
    const props = renderDialog({
      authenticated: false,
      authConfigured: true,
      allowLocalPreview: false,
    });
    await userEvent.click(screen.getByRole("button", { name: "Sign in to upgrade" }));
    expect(props.onSignIn).toHaveBeenCalledOnce();
  });

  it("explains when production sign-in has not been configured", async () => {
    renderDialog({
      authenticated: false,
      authConfigured: false,
      allowLocalPreview: false,
    });
    await userEvent.click(screen.getByRole("button", { name: "Sign in to upgrade" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sign-in must be configured before paid subscriptions can start.",
    );
  });
});
