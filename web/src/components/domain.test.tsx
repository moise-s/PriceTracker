import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { marketColor } from "@/lib/markets";
import { CoverageMeter, FreshnessBadge } from "./domain";

describe("FreshnessBadge", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-27T12:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("marks prices older than the freshness window as outdated", () => {
    render(<FreshnessBadge observedAt="2026-09-17T12:00:00Z" freshnessDays={7} />);
    expect(screen.getByText("Desatualizado · há 10 dias")).toBeInTheDocument();
  });
  it("highlights prices collected today", () => {
    render(<FreshnessBadge observedAt="2026-09-27T10:00:00Z" freshnessDays={7} />);
    expect(screen.getByText("Hoje · há 2 horas")).toBeInTheDocument();
  });
  it("says when there is no price at all", () => {
    render(<FreshnessBadge observedAt={null} freshnessDays={7} />);
    expect(screen.getByText("Sem preço")).toBeInTheDocument();
  });
});

describe("CoverageMeter", () => {
  it("exposes coverage as text, not only as colored segments", () => {
    render(<CoverageMeter covered={3} total={4} />);
    expect(screen.getByRole("img", { name: "3 de 4 itens encontrados" })).toBeInTheDocument();
    expect(screen.getByText(/de 4 itens encontrados/)).toBeInTheDocument();
  });
});

describe("marketColor", () => {
  it("uses the validated palette tokens for known markets", () => {
    expect(marketColor("bistek")).toBe("var(--color-market-bistek)");
    expect(marketColor("desconhecido", "#123456")).toBe("#123456");
    expect(marketColor(null)).toBe("var(--color-ink-3)");
  });
});
