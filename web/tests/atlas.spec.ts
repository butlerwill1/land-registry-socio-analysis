import { expect, test } from "@playwright/test";

test("loads the London map workspace and supports core filters", async ({ page }) => {
  await page.goto("/?demoPlan=pro");
  await expect(page.getByText("London Flat Atlas")).toBeVisible();
  await expect(page.getByRole("heading", { name: "SW11" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("London postcode district map")).toBeVisible();
  await expect(
    page.getByText(/Contains HM Land Registry data © Crown copyright and database right 2021/),
  ).toBeVisible();

  await page.getByLabel("Metric", { exact: true }).selectOption("overall");
  await expect(page.getByLabel("Overall deprivation score legend")).toBeVisible();

  await page.getByRole("button", { name: "LSOAs (2021)" }).click();
  await expect(page.getByText("SW11 · LSOA detail")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "LSOAs (2021)" })).toHaveAttribute(
    "aria-pressed",
    "true",
    { timeout: 30_000 },
  );
});

test("gates premium map detail and supports a local Pro preview", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Upgrade" })).toBeVisible();

  await page.getByRole("button", { name: "LSOAs (2021)" }).click();
  const pricing = page.getByRole("dialog", { name: "Choose your level of detail" });
  await expect(pricing).toBeVisible();
  await expect(pricing.getByText("£15")).toBeVisible();
  await expect(pricing.getByText("2021 LSOA-level map detail")).toBeVisible();

  await pricing.getByRole("button", { name: "Preview Pro locally" }).click();
  await expect(pricing).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Exit preview" })).toBeVisible();

  await page.getByRole("button", { name: "LSOAs (2021)" }).click();
  await expect(page.getByText("SW11 · LSOA detail")).toBeVisible({ timeout: 20_000 });
});

test("shows annual pricing and the launch disclaimer", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Upgrade" }).click();
  const pricing = page.getByRole("dialog", { name: "Choose your level of detail" });

  await pricing.getByRole("button", { name: /Annual/ }).click();
  await expect(pricing.getByText("£144")).toBeVisible();
  await expect(pricing.getByText("£12 per month, billed annually")).toBeVisible();
  await expect(pricing.getByText("Prices are launch hypotheses. VAT may apply.")).toBeVisible();
});

test("selects a postcode district from search", async ({ page }) => {
  await page.goto("/");
  const search = page.getByLabel("Find district");
  await search.fill("E8");
  await expect(search).toHaveAttribute("aria-expanded", "true");
  await search.press("Enter");
  await expect(page.getByRole("heading", { name: "E8" })).toBeVisible();
});

test("shows repaired Central London sales without inventing an LSOA summary", async ({ page }) => {
  await page.goto("/");
  const search = page.getByLabel("Find district");
  await search.fill("W1F");
  await search.press("Enter");

  await expect(page.getByRole("heading", { name: "W1F" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("No 2021 LSOA fits fully within")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("No data", { exact: true })).not.toBeVisible();
});

test("marks the latest transaction year as partial and explains reporting lag", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Next year" }).click();

  await expect(page.getByText("Partial", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Recent totals will rise as HM Land Registry records complete."),
  ).toBeVisible();
});

test("keeps district analysis available if the optional LSOA layer fails", async ({ page }) => {
  await page.route("**/data/lsoa-boundaries.geojson", (route) =>
    route.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page.goto("/?demoPlan=pro");
  await page.getByRole("button", { name: "LSOAs (2021)" }).click();
  await expect(page.getByText("LSOA detail could not load. Select it to retry.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "SW11" })).toBeVisible();
  await expect(page.getByLabel("London postcode district map")).toBeVisible();
});
