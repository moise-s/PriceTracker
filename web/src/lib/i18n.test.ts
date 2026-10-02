import { afterEach, describe, expect, it } from "vitest";
import { HEALTH, RUN_STATUS, TARGET_STATUS } from "./labels";
import { getLocale, setLocale, translate } from "./i18n";
import { money, parseMoneyInput, quantity, unitPrice } from "./format";

afterEach(() => setLocale("pt-BR"));
describe("local UI language", () => {
  it("persists the choice and changes the document language", () => {
    setLocale("en");
    expect(getLocale()).toBe("en");
    expect(localStorage.getItem("pricetracker.language")).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(translate("Monte sua lista")).toBe("Build your list");
    expect(RUN_STATUS.failed!.label).toBe("Failed");
    expect(TARGET_STATUS.running!.label).toBe("Searching");
    expect(HEALTH.saudavel!.label).toBe("Working");
    setLocale("pt-BR");
    expect(translate("Monte sua lista")).toBe("Monte sua lista");
    expect(RUN_STATUS.failed!.label).toBe("Falhou");
  });
  it("translates messages and preserves interpolated source names", () => {
    setLocale("en");
    expect(translate("Editar Pradão")).toBe("Edit Pradão");
    expect(translate("Anúncios encontrados para “Minha marca”." )).toBe("Anúncios encontrados para “Minha marca”.");
    expect(translate("Pradão")).toBe("Pradão");
    expect(translate("  Ordenar por Preço  ")).toBe("  Sort by Preço  ");
    expect(translate("Editar $&")).toBe("Edit $&");
  });
  it("formats decimal amounts in English without changing the currency", () => {
    setLocale("en");
    expect(money("1234.5")).toContain("1,234.50");
    expect(money("1234.5")).toContain("R$");
    expect(quantity("2", "pct")).toBe("2 packs");
    expect(unitPrice("0.0667", "m")).toContain("0.0667/m");
    expect(parseMoneyInput("1,234.56")).toBe(1234.56);
  });
  it("shows enough precision to distinguish prices per metre", () => {
    expect(unitPrice("0.0667", "m")).toContain("0,0667/m");
    expect(unitPrice("0.0670", "m")).toContain("0,0670/m");
  });
});
