import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { addToList, apiAs, createUser, expectNoClippedContent, expectNoHorizontalOverflow, login, PASSWORD, resetBackend, selectStores, snap } from "./support";

test.use({ reducedMotion: "reduce" });
test.beforeEach(async ({ request }) => { await resetBackend(request); });

test("English persists, keeps form edits and returns to the list after creation", async ({ page, request }, testInfo) => {
  await createUser(request, "english", { admin: true });
  await page.goto("/entrar");
  await page.getByRole("combobox", { name: "Idioma", exact: true }).selectOption("en");
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  await page.getByLabel("User", { exact: true }).fill("english");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/\/entrar/);
  await page.goto("/produtos/novo");
  await page.getByRole("button", { name: "Double-ply toilet paper", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Meu papel folha dupla");
  await page.getByRole("combobox", { name: "Language", exact: true }).selectOption("pt-BR");
  await expect(page.getByLabel("Nome", { exact: true })).toHaveValue("Meu papel folha dupla");
  await page.getByRole("combobox", { name: "Idioma", exact: true }).selectOption("en");
  await expect(page.getByRole("switch", { name: "Compare any pack size by price per metre" })).toBeChecked();
  await page.setViewportSize({ width: 320, height: 740 });
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
  await page.getByRole("button", { name: "Create product", exact: true }).click();
  await expect(page).toHaveURL(/\/lista$/);
  await expect(page.getByRole("heading", { name: "Build your list" })).toBeVisible();
  await page.getByRole("button", { name: "Add Meu papel folha dupla", exact: true }).click();
  await expect.poll(async () => {
    const lists = await apiAs(page, "GET", "/lists");
    return (await apiAs(page, "GET", `/lists/${lists[0].id}`)).items[0]?.unit;
  }).toBe("m");
  const lists = await apiAs(page, "GET", "/lists");
  const items = (await apiAs(page, "GET", `/lists/${lists[0].id}`)).items;
  expect(Number(items[0].quantity)).toBe(120);
  const products = await apiAs(page, "GET", "/products");
  expect(products[0].match_spec.required).toContainEqual(["papel higienico", "toilet paper"]);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Build your list" })).toBeVisible();
  await page.goto("/admin");
  await expect(page.getByRole("tab", { name: "Markets", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Markets", exact: true }).click();
  await page.getByRole("button", { name: "Add new market", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Test price source");
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
  await snap(page, testInfo, "english-admin-onboarding");
});

test("Home shows a new chain and reviews list then stores before starting", async ({ page, request }, testInfo) => {
  await createUser(request, "home-flow");
  await login(page, "home-flow");
  await addToList(page, ["Arroz"]);
  const all = await apiAs(page, "GET", "/markets");
  const fort = all.find((m: any) => m.slug === "fort");
  // Production API registration is covered by backend integration tests. Simulate
  // the newly registered chain here without a real network request to its site.
  const newMarket = { ...fort, id: "11111111-1111-4111-8111-111111111111", name: "Pradão", slug: "pradao", stores: [{ ...fort.stores[0], name: "Pradão Centro", selected: false }] };
  await page.route("**/api/v1/markets", async (route) => {
    const response = await route.fetch();
    const markets = await response.json();
    const existing = markets.find((m: any) => m.slug === "fort");
    await route.fulfill({ response, json: [...markets.filter((m: any) => m.slug !== "fort"), { ...newMarket, stores: [{ ...existing.stores[0], name: "Pradão Centro" }] }] });
  });
  await page.goto("/");
  const selection = page.getByRole("region", { name: "Mercados da próxima verificação" });
  await selection.locator("summary").filter({ hasText: "Pradão" }).click();
  await selection.getByRole("checkbox", { name: /Pradão Centro/ }).check();
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
  await snap(page, testInfo, "home-market-selection");
  expect((await apiAs(page, "GET", "/runs")).length).toBe(0);
  await page.getByRole("button", { name: "Atualizar preços", exact: true }).click();
  await expect(page).toHaveURL(/\/lista\?flow=price-check$/);
  await page.getByRole("link", { name: "Confirmar lista e escolher mercados" }).click();
  await expect(page).toHaveURL(/\/mercados\?flow=price-check$/);
  await expect(page.getByRole("checkbox", { name: /^Pradão Centro/ })).toBeChecked();
  expect((await apiAs(page, "GET", "/runs")).length).toBe(0);
  await page.getByRole("button", { name: "Verificar preços agora" }).first().click();
  await expect(page).toHaveURL(/\/buscas\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Resultado da busca" })).toBeVisible({ timeout: 30_000 });
});

test("history table sorts every column in either direction with accessible headers", async ({ page, request }, testInfo) => {
  await createUser(request, "sortable-history");
  await login(page, "sortable-history");
  await addToList(page, ["Arroz"]);
  await selectStores(page, ["angeloni"]);
  const products = await apiAs(page, "GET", "/products");
  const product = products[0];
  const point = { availability: "in_stock", method: "api", review_status: "ok", flagged: false, stale: false, unit_price_unit: "kg" };
  const series = [
    { market_name: "A Mercado", market_slug: "a", store_name: "Centro", store_id: "a", stats: { count: 2, last: "100", min: "9.5", max: "100", median: "54.75" }, points: [
      { ...point, observation_id: "a", observed_at: "2026-09-01T12:00:00Z", title: "Banana", price: "9.50", unit_price: "9.50" },
      { ...point, observation_id: "b", observed_at: "2026-09-02T12:00:00Z", title: "Abacate", price: "100.00", unit_price: "100.00", flagged: true, review_status: "flagged" },
    ] },
    { market_name: "B Mercado", market_slug: "b", store_name: "Bairro", store_id: "b", stats: { count: 1, last: null, min: null, max: null, median: null }, points: [
      { ...point, observation_id: "c", observed_at: "2026-09-03T12:00:00Z", title: "Café", price: null, unit_price: null, stale: true },
    ] },
  ];
  await page.route("**/api/v1/history/products/*?**", (route) => route.fulfill({ json: { product_id: product.id, product_name: product.name, freshness_days: 7, series } }));
  await page.goto("/historico");
  await page.getByRole("button", { name: "Ver tabela" }).click();
  const table = page.getByRole("table");
  const titles = () => table.locator("tbody tr td:nth-child(3)").allTextContents();
  const expected: Record<string, string[]> = { Data: ["Banana", "Abacate", "Café"], Loja: ["Banana", "Abacate", "Café"], Anúncio: ["Abacate", "Banana", "Café"], Preço: ["Banana", "Abacate", "Café"], "Por kg": ["Banana", "Abacate", "Café"], Situação: ["Banana", "Café", "Abacate"] };
  for (const [name, ascending] of Object.entries(expected)) {
    const header = table.getByRole("button", { name: `Ordenar por ${name}`, exact: true });
    await header.click();
    await expect(header.locator("..")).toHaveAttribute("aria-sort", "ascending");
    await expect.poll(titles).toEqual(ascending);
    await header.click();
    await expect(header.locator("..")).toHaveAttribute("aria-sort", "descending");
    await expect.poll(titles).toEqual(["Preço", "Por kg"].includes(name) ? ["Abacate", "Banana", "Café"] : name === "Loja" ? ["Café", "Banana", "Abacate"] : [...ascending].reverse());
  }
  const accessibility = await new AxeBuilder({ page }).include("table").analyze();
  expect(accessibility.violations).toEqual([]);
  await expectNoHorizontalOverflow(page);
  await snap(page, testInfo, "sortable-price-history");
});
