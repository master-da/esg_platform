import { expect, test } from "@playwright/test";
import { chooseCompany, login, logout, mobileCsv } from "./helpers";

const COMPANY = "Sample Textiles Ltd";

test("golden path: project -> upload -> categorize -> calculate -> review -> lock", async ({ page }) => {
  page.on("dialog", (d) => d.accept());
  const division = `E2E ${Date.now()}`;

  // 1. A sustainability manager creates a project (a unique division keeps repeated runs from overlapping).
  await login(page, "s.akter@sample.test");
  await page.goto("/environmental/projects");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.fill("#p-name", division);
  await page.fill("#p-start", "2025-01-01");
  await page.fill("#p-end", "2025-12-31");
  await page.selectOption("#p-boundary", "division");
  await page.fill("#p-div", division);
  await page.getByRole("button", { name: "Create project" }).last().click();
  await page.waitForURL(/\/environmental\/projects\/[0-9a-f-]{36}$/);
  const projectUrl = page.url();
  await expect(page.getByRole("heading", { name: division })).toBeVisible();

  // 2. Mobile combustion: a file with errors shows per-row issues and adds nothing.
  await page.getByRole("link", { name: /Mobile combustion/ }).click();
  await expect(page.getByText("Fuel used by vehicles the company owns")).toBeVisible();
  const fileInput = page.locator("input[type=file]").first();
  await fileInput.setInputFiles({
    name: "S1_Mobile_Mar.csv", mimeType: "text/csv",
    buffer: mobileCsv([["Gazipur Factory", "2025-03-01", "2025-03-31", "Padma Oil", "Delivery van", "Petrol", "", "L", "Estimate", ""]]),
  });
  await expect(page.getByText(/issue.* found/)).toBeVisible();
  await page.getByRole("button", { name: "Fix validation errors" }).click();
  await expect(page.getByText('"Petrol" is not in the fuel type list')).toBeVisible();
  await expect(page.getByText("Required field is empty")).toBeVisible();
  await page.getByRole("button", { name: "Back to files" }).click();

  // 3. A good file is accepted; rows wait for categorization.
  await fileInput.setInputFiles({
    name: "S1_Mobile_Jan.csv", mimeType: "text/csv",
    buffer: mobileCsv([
      ["Gazipur Factory", "2025-01-01", "2025-01-31", "Padma Oil", "Pick-up truck", "Diesel", "1200", "L", "Fuel receipts / fuel card", ""],
      ["Gazipur Factory", "2025-02-01", "2025-02-28", "Padma Oil", "Pick-up truck", "Diesel", "1.5", "t", "Supplier statement", ""],
      ["Dhaka Head Office", "2025-01-01", "2025-01-31", "Meghna Petroleum", "Car", "Petrol / Octane", "300", "L", "Fuel receipts / fuel card", ""],
    ]),
  });
  await expect(page.getByText(/3 rows added/)).toBeVisible();
  // Delete the failed file so the project can later be approved.
  const failedRow = page.getByRole("row", { name: /S1_Mobile_Mar\.csv/ });
  await failedRow.getByRole("button", { name: "File actions" }).click();
  await page.getByRole("menuitem", { name: "Delete file" }).click();
  await expect(page.getByRole("row", { name: /S1_Mobile_Mar\.csv/ })).toHaveCount(0);

  // 4. Categorization: rules suggest paths (never codes); a person accepts.
  await page.getByRole("tab", { name: /Data Categorization/ }).click();
  await expect(page.getByText("Mobile combustion › Road › Diesel")).toBeVisible();
  await expect(page.getByText("0 of 2 accepted")).toBeVisible();
  await page.getByRole("button", { name: /Accept all suggested \(2\)/ }).click();
  await expect(page.getByText("2 of 2 accepted")).toBeVisible();

  // 5. Data Overview -> calculated value -> full calculation trail.
  await page.getByRole("tab", { name: "Data Overview" }).click();
  await page.getByRole("button", { name: "Calculated values" }).click();
  await page.getByRole("button", { name: "3.1939" }).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByText("S1_Mobile_Jan.csv · row 2")).toBeVisible();
  await expect(sheet.getByText(/UK DESNZ GHG Conversion Factors/)).toBeVisible();
  await expect(sheet.getByText("3.19386 t CO₂e")).toBeVisible();
  await expect(sheet.getByText(/Factor code/)).toHaveCount(0);
  await page.keyboard.press("Escape");
  await logout(page);

  // 6. An internal reviewer confirms the file as Calculated.
  await login(page, "reviewer@platform.test");
  await chooseCompany(page, COMPANY);
  await page.goto(projectUrl);
  await page.getByRole("link", { name: /Mobile combustion/ }).click();
  const row = page.getByRole("row", { name: /S1_Mobile_Jan\.csv/ });
  await expect(row.getByText("Preliminary")).toBeVisible();
  await row.getByRole("button", { name: "File actions" }).click();
  await page.getByRole("menuitem", { name: "Confirm as Calculated" }).click();
  await expect(row.getByText("✓ Calculated")).toBeVisible();
  await logout(page);

  // 7. Approval only needs every uploaded file confirmed as Calculated; an approver then locks the project.
  await login(page, "s.akter@sample.test");
  await page.goto(projectUrl);
  for (const action of ["Start data collection", "Send for review", "Approve", "Lock project"]) {
    await page.getByRole("button", { name: action }).click();
    await expect(page.getByRole("button", { name: action })).toHaveCount(0);
  }
  await expect(page.getByText("LOCKED").first()).toBeVisible();
  await page.getByRole("link", { name: /Mobile combustion/ }).click();
  await expect(page.getByRole("button", { name: "Upload file" })).toHaveCount(0);

  // 8. Results show the category total and trails.
  await page.goto("/home/results");
  await page.getByLabel("Project").selectOption({ label: `${division} · LOCKED` });
  await expect(page.getByText("Scope 1 · Mobile combustion")).toBeVisible();

  // 9. Exports: the audit workbook, then the PDF report (only offered once a project is approved or locked).
  await page.goto("/home/reports");
  await page.getByLabel("Project").selectOption({ label: `${division} · LOCKED` });
  await page.getByRole("button", { name: /^Audit export/ }).click();
  await page.getByRole("button", { name: "Check data" }).click();
  const [audit] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /^Export/ }).click()]);
  expect(audit.suggestedFilename()).toMatch(/\.xlsx$/);
  await page.getByRole("button", { name: /^Custom/ }).click();
  await page.getByRole("button", { name: "PDF report" }).click();
  await page.getByRole("button", { name: "Check data" }).click();
  const [pdf] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /^Export/ }).click()]);
  expect(pdf.suggestedFilename()).toMatch(/\.pdf$/);
  const head = await new Promise<Buffer>((resolve, reject) => {
    pdf.createReadStream().then((s) => { const chunks: Buffer[] = []; s.on("data", (c) => chunks.push(c)); s.on("end", () => resolve(Buffer.concat(chunks))); s.on("error", reject); });
  });
  expect(head.subarray(0, 5).toString()).toBe("%PDF-");
  await expect(page.getByRole("row", { name: new RegExp(audit.suggestedFilename().replace(/[.]/g, "\\.")) })).toBeVisible();
});
