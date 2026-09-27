import { expect, test } from "@playwright/test";
import {
  addToList,
  apiAs,
  control,
  createUser,
  expectNoHorizontalOverflow,
  login,
  NEAR_ANGELONI_BEIRA_MAR,
  PASSWORD,
  resetBackend,
  runSearchFromUi,
  runSearchViaApi,
  selectStores,
  setFaults,
  setHome,
  snap,
  STORES,
} from "./support";

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("1. compra da semana: primeiro acesso, lista, lojas, busca e recomendação", async ({ page, request }, testInfo) => {
  const { code } = await control<{ code: string }>(request, "/setup-code");
  await page.goto("/");
  await expect(page).toHaveURL(/\/configurar$/);
  await page.getByLabel("Código de configuração").fill(code);
  await page.getByLabel("Seu nome").fill("Casa de Teste");
  await page.getByLabel("Nome de usuário").fill("e2e-admin");
  await page.getByLabel("Senha", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirme a senha").fill(PASSWORD);
  await page.getByRole("button", { name: "Criar administrador" }).click();

  await expect(page.getByRole("heading", { name: "Guarde seus códigos de recuperação" })).toBeVisible();
  await expect(page.locator("ol > li")).toHaveCount(10);
  await page.getByLabel("Guardei os códigos em um lugar seguro").check();
  await page.getByRole("button", { name: "Continuar" }).click();
  // Regression: the new admin used to be bounced past the welcome screen.
  await expect(page).toHaveURL(/\/boas-vindas$/);
  await page.getByRole("button", { name: /Começar pela lista/ }).click();
  await expect(page).toHaveURL(/\/lista$/);

  for (const name of ["Arroz branco 1 kg", "Feijão 1 kg", "Ovos 30 unidades", "Café Três Corações"]) {
    await page.getByRole("button", { name: new RegExp(`^Adicionar ${escape(name)}`) }).click();
    await expect(page.getByRole("button", { name: new RegExp(`^Adicionar ${escape(name)}`) })).toHaveCount(0);
  }
  await expect(page.getByText(/4 itens/).filter({ visible: true }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto("/mercados");
  for (const [market, store] of [["Angeloni", STORES.angeloni], ["Bistek", STORES.bistek], ["Fort Atacadista", STORES.fort]] as const) {
    const card = page.getByRole("region", { name: market, exact: true });
    const checkbox = card.getByRole("checkbox", { name: new RegExp(`^${escape(store)}`) });
    if (!(await checkbox.count())) await card.getByRole("button", { name: /Ver todas as/ }).click();
    await checkbox.check();
  }
  await expect(page.getByText("3 lojas selecionadas")).toBeVisible();
  await page.getByRole("button", { name: "Buscar preços" }).click();
  await expect(page).toHaveURL(/\/buscar$/);

  await page.getByRole("button", { name: "Buscar preços agora" }).click();
  await expect(page).toHaveURL(/\/buscas\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Resultado da busca" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Concluída", { exact: true }).filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "1-busca-concluida");

  await page.getByRole("link", { name: "Ver onde compensa" }).first().click();
  await expect(page).toHaveURL(/\/comparar$/);
  const headline = page.getByRole("heading", { level: 2, name: /^(Compre no|Divida a compra)/ });
  await expect(headline).toBeVisible();
  await expect(headline).toContainText("Fort Atacadista");
  await expect(page.getByText("4 de 4 itens encontrados").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText("Deslocamento ainda não incluído")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Item por item" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await snap(page, testInfo, "1-onde-compensa");
});

test("2. item faltante: cobertura honesta e sem vencedor injusto", async ({ page, request }, testInfo) => {
  await createUser(request, "e2e-bia");
  await login(page, "e2e-bia");
  await addToList(page, ["Arroz branco", "Feijão", "Maçã Fuji"]);
  await selectStores(page, ["angeloni", "fort"]);
  await runSearchFromUi(page);
  await page.goto("/comparar");

  // Fort has no Fuji apple: its cheaper partial basket must not win against a complete one.
  await expect(page.getByRole("heading", { level: 2, name: /Compre no Angeloni/ })).toBeVisible();
  await expect(page.getByText("3 de 3 itens encontrados").filter({ visible: true }).first()).toBeVisible();
  // The empty cell says why: the last search did not find an equivalent product.
  await expect(page.getByText("Não encontrado").filter({ visible: true }).first()).toBeVisible();

  await page.getByRole("tab", { name: "Cesta comum" }).click();
  await expect(page.getByText(/Fora da cesta comum.*Maçã Fuji/)).toBeVisible();
  await page.getByRole("tab", { name: "Por mercado" }).click();
  await expect(page.getByText("Total não comparável")).toBeVisible();
  await expect(page.getByText("2 de 3 itens encontrados").filter({ visible: true }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await snap(page, testInfo, "2-item-faltante");
});

test("3. deslocamento muda o vencedor", async ({ page, request }, testInfo) => {
  await createUser(request, "e2e-caio");
  await login(page, "e2e-caio");
  await addToList(page, ["Feijão", "Ovos", "Filtro de café"]);
  await selectStores(page, ["angeloni", "fort"]);
  await setHome(page, NEAR_ANGELONI_BEIRA_MAR);
  await apiAs(page, "PATCH", "/me/profile", { max_stops: 1 });
  await runSearchViaApi(page);
  await page.goto("/comparar");

  // With travel: home is next to Angeloni Beira Mar and ~12 km from Fort Kobrasol.
  const headline = page.getByRole("heading", { level: 2, name: /^Compre no/ });
  await expect(headline).toContainText("Angeloni");
  await expect(page.getByText(/km ÷ 10 km\/l × R\$ 6,29\/l/).filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "3-com-deslocamento");

  // Products only: Fort is R$ 3,31 cheaper (R$ 26,46 vs R$ 29,77).
  await page.getByRole("switch", { name: "Incluir deslocamento" }).click();
  await expect(headline).toContainText("Fort Atacadista");
  await expect(page.getByText("R$ 26,46").filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "3-sem-deslocamento");
});

test("4. IA indisponível: só os itens que precisam dela ficam pendentes", async ({ page, request }, testInfo) => {
  await createUser(request, "e2e-duda");
  await login(page, "e2e-duda");
  await addToList(page, ["Arroz branco", "Feijão"]);
  await selectStores(page, ["bistek", "fort"]);
  await setFaults(request, { bistek: "needs_llm" });
  await runSearchFromUi(page);

  await expect(page.getByText("Concluída com falhas").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText("Precisa de IA").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText(/não há IA configurada/).filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "4-ia-indisponivel-busca");

  await page.goto("/comparar");
  await expect(page.getByRole("heading", { level: 2, name: /Compre no Fort Atacadista/ })).toBeVisible();
  await expect(page.getByText("Precisa de IA").filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "4-ia-indisponivel-comparacao");
});

test("5. falha parcial: loja bloqueada é explicada e pode ser repetida", async ({ page, request }, testInfo) => {
  await createUser(request, "e2e-edu");
  await login(page, "e2e-edu");
  await addToList(page, ["Arroz branco", "Feijão"]);
  await selectStores(page, ["angeloni", "fort"]);
  await setFaults(request, { angeloni: "blocked" });
  await runSearchFromUi(page);

  await expect(page.getByText("Concluída com falhas").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText("Algumas consultas falharam")).toBeVisible();
  await expect(page.getByText("Bloqueado").filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "5-falha-parcial");

  // The site is reachable again: retry only the failed targets.
  await setFaults(request, {});
  await page.getByRole("button", { name: /Repetir falhas \(2\)/ }).click();
  await expect(page.getByRole("heading", { name: "Resultado da busca" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Concluída", { exact: true }).filter({ visible: true }).first()).toBeVisible();

  await page.goto("/comparar");
  await expect(page.getByText("2 de 2 itens encontrados").filter({ visible: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Cesta comum" }).click();
  await expect(page.getByText("Menor total")).toBeVisible();
  await snap(page, testInfo, "5-apos-repetir");
});

test("6. isolamento: um usuário nunca vê dados do outro", async ({ page, request, browser }, testInfo) => {
  await createUser(request, "e2e-ana");
  await createUser(request, "e2e-bruno");

  await login(page, "e2e-ana");
  const product = await apiAs(page, "POST", "/products", {
    name: "Granola da Ana",
    category: "Mercearia",
    sold_by: "package",
    package_quantity: "500",
    package_unit: "g",
  });
  await addToList(page, ["Arroz branco"]);
  await apiAs(page, "POST", `/lists/${(await apiAs(page, "GET", "/lists"))[0].id}/items`, { product_id: product.id });
  await selectStores(page, ["fort"]);
  await setHome(page, NEAR_ANGELONI_BEIRA_MAR);
  const runId = await runSearchViaApi(page);
  await page.goto("/lista");
  await expect(page.getByText("Granola da Ana").filter({ visible: true }).first()).toBeVisible();

  const other = await browser.newContext({ baseURL: testInfo.project.use.baseURL, viewport: testInfo.project.use.viewport ?? undefined });
  const bruno = await other.newPage();
  await login(bruno, "e2e-bruno");
  await bruno.goto("/lista");
  await expect(bruno.getByRole("heading", { name: "Monte sua lista" })).toBeVisible();
  await expect(bruno.getByText("Granola da Ana")).toHaveCount(0);
  await bruno.goto(`/produtos/${product.id}`);
  await expect(bruno.getByText(/não encontrado/i).filter({ visible: true }).first()).toBeVisible();
  await bruno.goto(`/buscas/${runId}`);
  await expect(bruno.getByText(/não encontrad/i).filter({ visible: true }).first()).toBeVisible();
  for (const path of [`/products/${product.id}`, `/runs/${runId}`]) {
    const response = await bruno.request.get(`/api/v1${path}`);
    expect(response.status(), path).toBe(404);
  }
  const addresses = await bruno.request.get("/api/v1/me/addresses");
  expect(await addresses.json()).toEqual([]);
  await bruno.goto("/comparar");
  await expect(bruno.getByText("Monte sua lista primeiro")).toBeVisible();
  await snap(bruno, testInfo, "6-isolamento-outro-usuario");
  await other.close();
});

test("7. frescor: preços antigos saem da recomendação até você autorizar", async ({ page, request }, testInfo) => {
  await createUser(request, "e2e-fabi");
  await login(page, "e2e-fabi");
  await addToList(page, ["Arroz branco", "Feijão"]);
  await selectStores(page, ["angeloni", "fort"]);
  await runSearchViaApi(page);
  await control(request, "/age-observations", { days: 10, username: "e2e-fabi" });
  await page.goto("/comparar");

  await expect(page.getByRole("heading", { name: "Ainda sem preços suficientes" })).toBeVisible();
  await expect(page.getByText("Desatualizado").filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "7-precos-antigos");

  await page.getByRole("switch", { name: "Usar preços desatualizados" }).click();
  await expect(page.getByText("Você autorizou o uso de preços antigos", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /^(Compre no|Divida a compra)/ })).toBeVisible();
  await expect(page.getByText("Confiança baixa").filter({ visible: true }).first()).toBeVisible();
  await snap(page, testInfo, "7-antigos-autorizados");
});
