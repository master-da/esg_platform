import { expect, type Page } from "@playwright/test";

export const PASSWORD = "Password123!";

export async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/login/);
}

export async function chooseCompany(page: Page, name: string) {
  const select = page.getByLabel("Active company");
  if (await select.count()) {
    await select.selectOption({ label: name });
    await expect(select).toHaveValue(/.+/);
    await page.waitForLoadState("networkidle");
  }
}

/** CSV with the mobile combustion template's headers (detected by header signature). */
export function mobileCsv(rows: string[][]): Buffer {
  const header = ["Facility", "Period start", "Period end", "Fuel supplier", "Vehicle type", "Fuel type", "Fuel quantity", "Unit", "Data basis", "Notes"];
  return Buffer.from([header, ...rows].map((r) => r.map((c) => (c.includes(",") ? `"${c}"` : c)).join(",")).join("\n") + "\n");
}
