import { expect, test } from "@playwright/test";

test("loads the London map workspace and supports core filters", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("London Flat Atlas")).toBeVisible();
  await expect(page.getByRole("heading", { name: "SW11" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("London postcode district map")).toBeVisible();

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
  await page.goto("/");
  await page.getByRole("button", { name: "LSOAs (2021)" }).click();
  await expect(page.getByText("LSOA detail could not load. Select it to retry.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "SW11" })).toBeVisible();
  await expect(page.getByLabel("London postcode district map")).toBeVisible();
});
