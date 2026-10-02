import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { addToList, apiAs, createUser, expectNoClippedContent, expectNoHorizontalOverflow, login, resetBackend, snap } from "./support";

test.use({ reducedMotion: "reduce" });
test.beforeEach(async ({ request }) => { await resetBackend(request); });

test("todos os produtos do catálogo são editáveis, com alterações pessoais", async ({ page, request }, testInfo) => {
  await createUser(request, "eggs-editor");
  await login(page, "eggs-editor");
  await page.goto("/lista");
  await page.getByRole("button", { name: "Editar Ovos 30 unidades", exact: true }).click();
  await expect(page).toHaveURL(/\/produtos\/[0-9a-f-]{36}$/);
  const listsBefore = await apiAs(page, "GET", "/lists");
  expect(listsBefore[0].item_count).toBe(0); // Editing alone does not add a list item.
  await page.getByLabel("Nome", { exact: true }).fill("Ovos da minha região 30 unidades");
  const products = await apiAs(page, "GET", "/products");
  const original = products.find((p: any) => p.name === "Ovos 30 unidades");
  await page.getByRole("button", { name: "Salvar alterações", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Ovos da minha região 30 unidades", exact: true })).toBeVisible();
  const updated = await apiAs(page, "GET", `/products/${original.id}`);
  expect(updated.match_spec.required).toEqual(original.match_spec.required);
  await page.goto("/lista");
  await expect(page.getByText("Ovos da minha região 30 unidades", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Adicionar Ovos da minha região 30 unidades", exact: true }).click();
  await addToList(page, ["Arroz", "Feijão", "Café"]);
  await page.reload();
  await expect(page.getByRole("button", { name: "Na lista (4)", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
  await snap(page, testInfo, "lista-editavel");
  if (testInfo.project.name === "desktop") {
    const sidebar = page.getByRole("complementary", { name: "Sua lista" });
    await expect(sidebar.getByRole("link", { name: "Ovos da minha região 30 unidades", exact: true })).toBeVisible();
    await expect(sidebar.getByRole("group", { name: /quantidade de Ovos/ })).toBeVisible();
  }
  const catalog = await apiAs(page, "GET", "/catalog");
  expect(catalog.items.some((i: any) => i.name === "Ovos 30 unidades")).toBe(true);
  await page.setViewportSize({ width: 320, height: 740 });
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
});

test("a escolha de mercados inicia uma verificação diretamente", async ({ page, request }) => {
  await createUser(request, "quick-search");
  await login(page, "quick-search");
  await page.goto("/mercados");
  await expect(page.getByRole("button", { name: "Verificar preços agora" }).first()).toBeDisabled();
  await addToList(page, ["Arroz"]);
  await page.reload();
  await page.getByLabel("Buscar mercado ou filial").fill("beira mar");
  await page.getByRole("checkbox", { name: /^Beira Mar/ }).check();
  await page.setViewportSize({ width: 320, height: 740 });
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
  await expect(page.getByRole("button", { name: "Verificar preços agora" }).first()).toBeEnabled();
  await page.getByRole("button", { name: "Verificar preços agora" }).first().click();
  await expect(page).toHaveURL(/\/buscas\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Resultado da busca" })).toBeVisible({ timeout: 30_000 });
  const run = await apiAs(page, "GET", `/runs/${page.url().split("/").pop()}`);
  expect(run.total_targets).toBe(1);
  expect(run.counts.found).toBe(1);
});

test("assistente testa uma fonte nova, explica falhas e pede revisão antes de ativar", async ({ page, request }, testInfo) => {
  await createUser(request, "onboarding-admin", { admin: true });
  await login(page, "onboarding-admin");
  let supported = false;
  let created: any = null;
  let updatedSource: any = null;
  const newMarket = { id: "11111111-1111-4111-8111-111111111111", name: "Mercado Independente", slug: "mercado-independente", website: "https://mercado.example", adapter_key: "public_jsonld", enabled: true, brand_color: "#194C81", notes: "Referência online pública", context_kind: "shared", context_help: "Referência online pública", sitemap_url: "https://mercado.example/sitemap.xml", stores: [{ id: "22222222-2222-4222-8222-222222222222", slug: "centro", name: "Centro", city: "Curitiba", state: "PR", is_active: true, source: "admin" }] };
  // HTTP source checks are exercised in the backend integration suite. Here the
  // UI gets deterministic responses without consulting an external website.
  await page.route("**/api/v1/admin/markets/probe", async (route) => {
    await route.fulfill({ json: { supported, reason: supported ? "Fonte reconhecida" : "A página não publica preço em BRL.", website: "https://mercado.example", sitemap_url: route.request().postDataJSON().sitemap_url || "https://mercado.example/sitemap.xml", sample_name: supported ? "Arroz branco 1 kg" : null, sample_price: supported ? "7.49" : null, indexed_pages: supported ? 10 : 0, price_scope_note: "Preço online público de referência; não confirma o preço da filial nem a região de entrega." } });
  });
  await page.route("**/api/v1/admin/markets", async (route) => {
    if (route.request().method() === "POST") {
      created = route.request().postDataJSON();
      await route.fulfill({ status: 201, json: newMarket });
    } else {
      const response = await route.fetch();
      const data = await response.json();
      await route.fulfill({ response, json: created ? [...data, newMarket] : data });
    }
  });
  await page.route(`**/api/v1/admin/markets/${newMarket.id}/source`, async (route) => {
    updatedSource = route.request().postDataJSON();
    newMarket.sitemap_url = updatedSource.sitemap_url;
    await route.fulfill({ json: newMarket });
  });
  await page.goto("/admin");
  await page.getByRole("tab", { name: "Mercados", exact: true }).click();
  await page.getByRole("button", { name: "Adicionar novo mercado", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Site do mercado", { exact: true }).fill("https://mercado.example");
  await dialog.getByLabel("Link de um produto com preço", { exact: true }).fill("https://mercado.example/arroz-branco-1kg");
  await dialog.getByRole("button", { name: "Testar site", exact: true }).click();
  await expect(dialog.getByText("Este site ainda não está pronto para coleta")).toBeVisible();
  expect(created).toBeNull();
  supported = true;
  await dialog.getByRole("button", { name: "Testar site", exact: true }).click();
  await expect(dialog.getByText("Fonte reconhecida", { exact: true })).toBeVisible();
  const activate = dialog.getByRole("button", { name: "Cadastrar e ativar mercado", exact: true });
  await expect(activate).toBeDisabled();
  await dialog.getByLabel("Nome da nova rede", { exact: true }).fill("Mercado Independente");
  await dialog.getByLabel("Nome da primeira loja", { exact: true }).fill("Centro");
  await dialog.getByLabel("Cidade", { exact: true }).fill("Curitiba");
  await dialog.getByLabel("UF", { exact: true }).selectOption("PR");
  if (testInfo.project.name === "mobile") await page.setViewportSize({ width: 320, height: 740 });
  await expectNoHorizontalOverflow(page);
  await expectNoClippedContent(page);
  await snap(page, testInfo, "onboarding-novo-mercado");
  const accessibility = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
  expect(accessibility.violations).toEqual([]);
  await dialog.getByRole("checkbox", { name: /Conferi o preço de exemplo/ }).check();
  await activate.click();
  await expect(dialog).not.toBeVisible();
  expect(created).toMatchObject({ name: "Mercado Independente", confirm_public_price: true, first_store: { name: "Centro", city: "Curitiba", state: "PR" } });
  const added = page.getByRole("region", { name: "Gerenciar Mercado Independente" });
  await added.getByRole("button", { name: "Revalidar fonte" }).click();
  await expect(dialog.getByLabel("Site do mercado", { exact: true })).toHaveAttribute("readonly", "");
  await dialog.getByLabel("Link de um produto com preço", { exact: true }).fill("https://mercado.example/arroz-branco-1kg");
  await dialog.getByLabel("Índice de produtos (opcional)", { exact: true }).fill("https://mercado.example/produtos.xml");
  await dialog.getByRole("button", { name: "Testar site", exact: true }).click();
  await dialog.getByRole("checkbox", { name: /Conferi o preço de exemplo/ }).check();
  await dialog.getByRole("button", { name: "Salvar fonte validada", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(updatedSource).toMatchObject({ sitemap_url: "https://mercado.example/produtos.xml", confirm_public_price: true });
  await expect(added.getByText(/índice: https:\/\/mercado.example\/produtos.xml/)).toBeVisible();
});
