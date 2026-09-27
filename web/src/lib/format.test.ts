import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ago, ageDays, km, money, packageLabel, parseMoneyInput, pluralize, quantity, unitPrice } from "./format";

// Intl uses a non-breaking space between "R$" and the amount.
const nb = (text: string) => text.replace(/ /g, " ");

describe("money", () => {
  it("formats decimal strings from the API as BRL", () => {
    expect(nb(money("1234.5"))).toBe("R$ 1.234,50");
    expect(nb(money("0.1"))).toBe("R$ 0,10");
  });
  it("shows a dash instead of inventing a value", () => {
    expect(money(null)).toBe("—");
    expect(money("")).toBe("—");
    expect(money("abc")).toBe("—");
  });
});

describe("units and quantities", () => {
  it("keeps list quantity separate from package size", () => {
    expect(quantity("2", "pct")).toBe("2 pacotes");
    expect(quantity("1", "un")).toBe("1 unidade");
    expect(quantity("0.5", "kg")).toBe("500 g");
    expect(quantity("1.25", "kg")).toBe("1,25 kg");
  });
  it("labels how a product is sold", () => {
    expect(packageLabel("400", "g", "package")).toBe("400 g");
    expect(packageLabel(null, null, "weight")).toBe("por kg");
    expect(packageLabel("30", "un", "package")).toBe("30 un");
  });
  it("formats comparable unit prices and distances", () => {
    expect(nb(unitPrice("17.475", "kg"))).toBe("R$ 17,48/kg");
    expect(unitPrice(null, "kg")).toBe("—");
    expect(km("29.34")).toBe("29,3 km");
  });
  it("pluralizes Portuguese nouns", () => {
    expect(pluralize(1, "item", "itens")).toBe("1 item");
    expect(pluralize(4, "item", "itens")).toBe("4 itens");
  });
});

describe("relative time", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-27T12:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("describes observation age", () => {
    expect(ago("2026-09-27T11:59:30Z")).toBe("agora");
    expect(ago("2026-09-27T09:00:00Z")).toBe("há 3 horas");
    expect(ago("2026-09-19T12:00:00Z")).toBe("há 8 dias");
    expect(ago(null)).toBe("nunca");
  });
  it("computes age in days for freshness checks", () => {
    expect(ageDays("2026-09-20T12:00:00Z")).toBe(7);
    expect(ageDays(undefined)).toBeNull();
  });
});

describe("parseMoneyInput", () => {
  it("accepts pt-BR and dot decimals", () => {
    expect(parseMoneyInput("7,50")).toBe(7.5);
    expect(parseMoneyInput("R$ 1.234,56")).toBe(1234.56);
    expect(parseMoneyInput("7.5")).toBe(7.5);
  });
  it("rejects anything that is not a positive amount", () => {
    for (const text of ["", "0", "-3", "abc", "7,555", "1,2,3"]) expect(parseMoneyInput(text), text).toBeNull();
  });
});
