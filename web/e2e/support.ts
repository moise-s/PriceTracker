import { expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";

export const API_URL = `http://127.0.0.1:${process.env.E2E_API_PORT ?? 8765}`;
export const PASSWORD = "e2e-senha-forte-123";

/** Stores whose responses were captured in the fixtures (tests/fixtures). */
export const STORES = {
  angeloni: "Beira Mar",
  bistek: "Costeira do Pirajubaé (Florianópolis)",
  fort: "Kobrasol",
  imperatriz: "Mauro Ramos (Florianópolis)",
} as const;
export type MarketSlug = keyof typeof STORES;

/** Public reference points (not anyone's address). */
export const NEAR_ANGELONI_BEIRA_MAR = { latitude: "-27.576000", longitude: "-48.529000" };
export const CITY_CENTER = { latitude: "-27.596900", longitude: "-48.549500" };

type Fault = "blocked" | "timeout" | "broken" | "needs_llm";

export async function control<T = unknown>(request: APIRequestContext, path: string, data: unknown = {}): Promise<T> {
  const response = await request.post(`${API_URL}/__e2e${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

export const resetBackend = (request: APIRequestContext) => control(request, "/reset");
export const setFaults = (request: APIRequestContext, faults: Partial<Record<MarketSlug, Fault>>, latencyMs = 0) =>
  control(request, "/faults", { faults, latency_ms: latencyMs });
export const createUser = (request: APIRequestContext, username: string, extra: { admin?: boolean; display_name?: string } = {}) =>
  control<{ id: string }>(request, "/users", { username, password: PASSWORD, ...extra });

export async function login(page: Page, username: string, password = PASSWORD) {
  await page.goto("/entrar");
  await page.getByLabel("Usuário").fill(username);
  await page.getByLabel("Senha").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).not.toHaveURL(/\/entrar/);
  await expect(page.getByRole("main")).toBeVisible();
}

/** Calls the real API as the signed-in browser user (same cookies + CSRF token). */
export async function apiAs<T = any>(page: Page, method: string, path: string, data?: unknown): Promise<T> {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((c) => c.name === "pt_csrf")?.value ?? "";
  const origin = new URL(page.url().startsWith("http") ? page.url() : "http://localhost:4173").origin;
  const response = await page.request.fetch(`/api/v1${path}`, {
    method,
    data,
    headers: { "X-CSRF-Token": csrf, Origin: origin },
  });
  expect(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return (response.status() === 204 ? null : await response.json()) as T;
}

export async function addToList(page: Page, names: string[]) {
  const lists = await apiAs(page, "GET", "/lists");
  const listId = lists[0].id as string;
  const catalog = await apiAs(page, "GET", "/catalog");
  for (const name of names) {
    const item = catalog.items.find((entry: { name: string }) => entry.name.startsWith(name));
    expect(item, `catalog item ${name}`).toBeTruthy();
    await apiAs(page, "POST", `/lists/${listId}/items`, { catalog_item_id: item.id });
  }
  return listId;
}

export async function selectStores(page: Page, markets: MarketSlug[]) {
  const all = await apiAs(page, "GET", "/markets");
  const ids = markets.map((slug) => {
    const market = all.find((m: { slug: string }) => m.slug === slug);
    const store = market?.stores.find((s: { name: string }) => s.name === STORES[slug]);
    expect(store, `${slug} store ${STORES[slug]}`).toBeTruthy();
    return store.id as string;
  });
  await apiAs(page, "PUT", "/me/stores", { selections: ids.map((store_id) => ({ store_id })) });
  return ids;
}

export async function setHome(page: Page, point: { latitude: string; longitude: string }, vehicle = { km_per_liter: "10", fuel_price_per_liter: "6.29" }) {
  await apiAs(page, "POST", "/me/addresses", { label: "Casa", city: "Florianópolis", state: "SC", ...point });
  await apiAs(page, "POST", "/me/vehicles", { name: "Carro", fuel_type: "gasolina", ...vehicle });
}

/** Starts a collection from the UI and waits for the finished run page. Returns the run id. */
export async function runSearchFromUi(page: Page) {
  await page.goto("/buscar");
  await page.getByRole("button", { name: "Buscar preços agora" }).click();
  await expect(page).toHaveURL(/\/buscas\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Resultado da busca" })).toBeVisible({ timeout: 30_000 });
  return page.url().split("/").pop()!;
}

export async function runSearchViaApi(page: Page) {
  const run = await apiAs(page, "POST", "/runs", {});
  await expect
    .poll(async () => (await apiAs(page, "GET", `/runs/${run.id}`)).status, { timeout: 30_000 })
    .toMatch(/success|partial|failed|cancelled/);
  return run.id as string;
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
}

/** Saves a screenshot next to the test results and attaches it to the HTML report. */
export async function snap(page: Page, testInfo: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  const path = testInfo.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true, animations: "disabled" });
  await testInfo.attach(name, { path, contentType: "image/png" });
}
