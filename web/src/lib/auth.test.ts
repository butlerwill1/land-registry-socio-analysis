import { describe, expect, it } from "vitest";
import { initialiseAuthentication, isAuthConfigured, signIn } from "./auth";

describe("OIDC authentication", () => {
  it("reports authentication as disabled without build-time OIDC settings", () => {
    expect(isAuthConfigured()).toBe(false);
  });

  it("leaves anonymous local sessions usable when OIDC is disabled", async () => {
    await expect(initialiseAuthentication()).resolves.toBe(false);
  });

  it("rejects an attempted production sign-in when OIDC is disabled", async () => {
    await expect(signIn()).rejects.toThrow("OIDC authentication is not configured.");
  });
});
