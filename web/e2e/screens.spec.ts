import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  addToList,
  apiAs,
  CITY_CENTER,
  control,
  createUser,
  login,
  resetBackend,
  runSearchViaApi,
  selectStores,
  setHome,
} from "./support";

// Committed evidence for the docs: every main screen at 360/390/1280/1440 px, light + dark.
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots");
const WIDTHS = [360, 390, 1280, 1440] as const;
const ALL_ITEMS = [
  "Arroz branco",
  "Feijão",
  "Lentilha",
  "Ovos",
  "Alcatra",
  "Maminha",
  "Café Três Corações",
  "Filtro de café",
  "Maçã Fuji",
  "Mamão",
];

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByText(/^Carregando/)).toHaveCount(0);
}

/** Elements sticking out of the viewport. `main` clips horizontally, so page-level scrollWidth
 * alone would hide content that is cut off at the edge; this finds it. Content inside deliberate
 * horizontal scrollers or inside boxes that clip their own decorations is ignored. */
async function clippedAtEdge(page: Page) {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const offenders: string[] = [];
    for (const el of Array.from(document.querySelectorAll("main *"))) {
      const rect = el.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2 || (rect.right <= width + 1 && rect.left >= -1)) continue;
      const style = getComputedStyle(el);
      if (style.opacity === "0" || style.visibility === "hidden" || el.closest("[aria-hidden='true']")) continue;
      let contained = false;
      for (let node = el.parentElement; node && node.tagName !== "MAIN"; node = node.parentElement) {
        const overflow = getComputedStyle(node).overflowX;
        if (overflow === "auto" || overflow === "scroll") contained = true;
        if ((overflow === "hidden" || overflow === "clip") && node.getBoundingClientRect().right <= width + 1) contained = true;
        if (contained) break;
      }
      if (contained) continue;
      const label = `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}.${Array.from(el.classList).slice(0, 4).join(".")}`;
      offenders.push(`${label} [${Math.round(rect.left)}→${Math.round(rect.right)}] "${(el.textContent ?? "").trim().slice(0, 40)}"`);
    }
    return offenders.slice(0, 4);
  });
}

async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.length}× ${v.nodes[0]?.target.join(" ")}`);
}

test("telas principais em 360/390/1280/1440, sem rolagem horizontal nem violações graves de acessibilidade", async ({ page, request }) => {
  test.setTimeout(300_000);
  await resetBackend(request);
  await createUser(request, "e2e-casa", { display_name: "Casa", admin: true });
  await login(page, "e2e-casa");
  await addToList(page, ALL_ITEMS);
  await selectStores(page, ["angeloni", "bistek", "fort", "imperatriz"]);
  await setHome(page, CITY_CENTER, { km_per_liter: "11", fuel_price_per_liter: "6.29" });
  // Two collections six days apart so the history chart shows a trend.
  await runSearchViaApi(page);
  await control(request, "/age-observations", { days: 6, username: "e2e-casa", price_factor: "1.08" });
  const runId = await runSearchViaApi(page);

  // A custom product with a photo uploaded through the product form.
  const product = await apiAs(page, "POST", "/products", {
    name: "Granola artesanal",
    category: "Mercearia",
    sold_by: "package",
    package_quantity: "500",
    package_unit: "g",
  });
  await apiAs(page, "POST", `/lists/${(await apiAs(page, "GET", "/lists"))[0].id}/items`, { product_id: product.id });
  await page.goto(`/produtos/${product.id}`);
  await page.locator('input[type="file"]').setInputFiles(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "fixtures/granola.png"));
  await expect(page.getByText("Imagem atualizada")).toBeVisible();

  const screens: Array<[string, string]> = [
    ["inicio", "/"],
    ["lista", "/lista"],
    ["mercados", "/mercados"],
    ["busca", `/buscas/${runId}`],
    ["onde-compensa", "/comparar"],
    ["historico", "/historico"],
    ["produto", `/produtos/${product.id}`],
    ["perfil", "/perfil"],
    ["admin", "/admin"],
  ];
  const problems: string[] = [];
  for (const width of WIDTHS) {
    mkdirSync(path.join(OUT, String(width)), { recursive: true });
    await page.setViewportSize({ width, height: width < 768 ? 800 : 900 });
    for (const [name, url] of screens) {
      await page.goto(url);
      await settle(page);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 0) problems.push(`${name}@${width}: ${overflow}px de rolagem horizontal`);
      for (const offender of await clippedAtEdge(page)) problems.push(`${name}@${width}: cortado na borda: ${offender}`);
      await page.screenshot({ path: path.join(OUT, String(width), `${name}.jpg`), fullPage: true, type: "jpeg", quality: 72, animations: "disabled" });
      if (width === 390 || width === 1280) {
        for (const violation of await seriousViolations(page)) problems.push(`${name}@${width}: ${violation}`);
      }
    }
  }

  await page.emulateMedia({ colorScheme: "dark" });
  mkdirSync(path.join(OUT, "dark"), { recursive: true });
  for (const width of [390, 1280] as const) {
    await page.setViewportSize({ width, height: width < 768 ? 800 : 900 });
    for (const [name, url] of [["inicio", "/"], ["onde-compensa", "/comparar"], ["historico", "/historico"]] as const) {
      await page.goto(url);
      await settle(page);
      await page.screenshot({ path: path.join(OUT, "dark", `${name}-${width}.jpg`), fullPage: true, type: "jpeg", quality: 72, animations: "disabled" });
      for (const violation of await seriousViolations(page)) problems.push(`dark ${name}@${width}: ${violation}`);
    }
  }
  expect(problems, problems.join("\n")).toEqual([]);
});
