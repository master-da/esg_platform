import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Minimal one-page PDF so the upload has a real document to preview.
const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj " +
  "3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF",
);

test("electricity bill: upload, review, confirm as USER_VERIFIED", async ({ page }) => {
  const division = `Bill ${Date.now()}`;
  await login(page, "s.akter@sample.test");
  await page.goto("/environmental/projects");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.fill("#p-name", division);
  await page.fill("#p-start", "2026-01-01");
  await page.fill("#p-end", "2026-12-31");
  await page.selectOption("#p-boundary", "division");
  await page.fill("#p-div", division);
  await page.getByRole("button", { name: "Create project" }).last().click();
  await page.waitForURL(/\/environmental\/projects\/[0-9a-f-]{36}$/);
  await page.getByRole("link", { name: /Purchased electricity/ }).click();

  await page.locator("input[type=file][accept^='application/pdf']").setInputFiles({ name: "DESCO_Jan.pdf", mimeType: "application/pdf", buffer: PDF });
  await page.waitForURL(/\/bills\/[0-9a-f-]{36}$/);
  await expect(page.getByText("Extracted fields")).toBeVisible();
  await expect(page.getByText("Nothing is saved until you confirm")).toBeVisible();

  const row = (label: string) => page.getByRole("row", { name: new RegExp(label) }).getByRole("textbox").first();
  await page.getByRole("row", { name: /Billing period start/ }).locator("input").fill("2026-01-01");
  await page.getByRole("row", { name: /Billing period end/ }).locator("input").fill("2026-01-31");
  await row("kWh consumed").fill("125000");
  await row("Utility").fill("DESCO");
  await page.getByRole("button", { name: /Confirm/ }).click();
  await page.waitForURL(/\/environmental\/projects\/[0-9a-f-]{36}\/s2_electricity$/);
  await expect(page.getByRole("row", { name: /DESCO_Jan\.pdf/ })).toBeVisible();
  await page.getByRole("tab", { name: "Data Overview" }).click();
  await expect(page.getByText("125,000 kWh").first()).toBeVisible();
});
