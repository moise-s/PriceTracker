import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Schemas } from "@/api/client";
import { RecommendationCard } from "./recommendation";

const ANGELONI = "11111111-1111-1111-1111-111111111111";
const FORT = "22222222-2222-2222-2222-222222222222";
const BISTEK = "33333333-3333-3333-3333-333333333333";

function comparison(overrides: Partial<Schemas["RecommendationOut"]> = {}) {
  return {
    include_travel: true,
    freshness_days: 7,
    stores: [
      { store_id: ANGELONI, market_slug: "angeloni", market_name: "Angeloni", store_name: "Beira Mar" },
      { store_id: FORT, market_slug: "fort", market_name: "Fort Atacadista", store_name: "Kobrasol" },
      { store_id: BISTEK, market_slug: "bistek", market_name: "Bistek", store_name: "Costeira" },
    ],
    plan: {
      best: { travel: { method: "estimate", formula: "25,5 km ÷ 11 km/l × R$ 6,29/l + R$ 0,00 de pedágio = R$ 14,58" } },
      assumptions: ["Divisão só quando economiza pelo menos R$ 5,00."],
    },
    recommendation: {
      kind: "split",
      store_ids: [ANGELONI, FORT],
      headline: "Divida a compra entre Angeloni e Fort Atacadista",
      explanation: ["Produtos: R$ 166,68", "Deslocamento: R$ 14,58"],
      products_total: "166.68",
      travel_total: "14.58",
      effective_total: "181.26",
      savings: "52.52",
      savings_reference_store_id: BISTEK,
      covered: 10,
      total_items: 11,
      newest_observed_at: new Date().toISOString(),
      oldest_observed_at: new Date().toISOString(),
      confidence: "media",
      confidence_reasons: ["Cobertura parcial: 10 de 11 itens."],
      warnings: ["Sem preço utilizável em nenhum mercado: Granola artesanal."],
      ...overrides,
    },
  } as unknown as Schemas["ComparisonOut"];
}

describe("RecommendationCard", () => {
  it("separates products, travel and total, and names the stores", () => {
    render(<RecommendationCard comparison={comparison()} colors={{}} />);
    expect(screen.getByRole("heading", { level: 2, name: "Divida a compra entre Angeloni e Fort Atacadista" })).toBeInTheDocument();
    expect(screen.getByText("Total com deslocamento")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Total: R\$\s181,26$/)).toBeInTheDocument();
    expect(screen.getByText("Produtos").parentElement).toHaveTextContent(/R\$\s166,68/);
    expect(screen.getByText("Deslocamento").parentElement).toHaveTextContent(/R\$\s14,58/);
    expect(screen.getByText(/Economia de R\$\s52,52/)).toBeInTheDocument();
    expect(screen.getByText("vs. Bistek Costeira")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "10 de 11 itens encontrados" })).toBeInTheDocument();
    expect(screen.getByText("Confiança média")).toBeInTheDocument();
  });

  it("shows the travel formula and never hides warnings", () => {
    render(<RecommendationCard comparison={comparison()} colors={{}} />);
    expect(screen.getByText(/25,5 km ÷ 11 km\/l × R\$ 6,29\/l/)).toBeInTheDocument();
    expect(screen.getByText(/Granola artesanal/)).toBeInTheDocument();
  });

  it("explains the recommendation on demand", () => {
    render(<RecommendationCard comparison={comparison()} colors={{}} />);
    expect(screen.queryByText("Cobertura parcial: 10 de 11 itens.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Por que esta recomendação/ }));
    expect(screen.getByText("Cobertura parcial: 10 de 11 itens.")).toBeInTheDocument();
    expect(screen.getByText(/Divisão só quando economiza/)).toBeInTheDocument();
  });

  it("renders nothing when there is not enough data to recommend", () => {
    const { container } = render(<RecommendationCard comparison={comparison({ kind: "none", store_ids: [] })} colors={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
