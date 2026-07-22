import { expect, test } from "@playwright/test";

test("loads the London map workspace and supports core filters", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("London Flat Atlas")).toBeVisible();
  await expect(page.getByRole("heading", { name: "SW11" })).toBeVisible();
  await expect(page.getByLabel("London postcode district map")).toBeVisible();

  await page.getByLabel("Metric").selectOption("overall");
  await expect(page.getByLabel("Overall deprivation score legend")).toBeVisible();

  await page.getByRole("button", { name: "LSOAs (2021)" }).click();
  await expect(page.getByText("SW11 · LSOA detail")).toBeVisible({ timeout: 20_000 });
});

test("selects a postcode district from search", async ({ page }) => {
  await page.goto("/");
  const search = page.getByLabel("Find district");
  await search.fill("E8");
  await page.getByRole("option", { name: /E8/ }).click();
  await expect(page.getByRole("heading", { name: "E8" })).toBeVisible();
});
