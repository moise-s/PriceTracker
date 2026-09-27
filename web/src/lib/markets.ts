const KNOWN_MARKETS = new Set(["angeloni", "bistek", "fort", "imperatriz"]);

/** Market identity colour: CSS token (with a validated dark step) when known. */
export function marketColor(slug: string | null | undefined, fallback?: string | null): string {
  if (slug && KNOWN_MARKETS.has(slug)) return `var(--color-market-${slug})`;
  return fallback ?? "var(--color-ink-3)";
}
