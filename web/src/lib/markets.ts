const KNOWN_MARKETS = new Set(["angeloni", "bistek", "fort", "imperatriz"]);
const DEFAULT_COLORS: Record<string, string> = { angeloni: "#1BAF7A", bistek: "#4A3AA7", fort: "#EB6834", imperatriz: "#2A78D6" };

/** Market identity colour: CSS token (with a validated dark step) when known. */
export function marketColor(slug: string | null | undefined, fallback?: string | null): string {
  if (slug && fallback && fallback.toUpperCase() !== DEFAULT_COLORS[slug]?.toUpperCase()) return fallback;
  if (slug && KNOWN_MARKETS.has(slug)) return `var(--color-market-${slug})`;
  return fallback ?? "var(--color-ink-3)";
}
export const STATES = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

export function filterText(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR").trim();
}
