import type { LucideIcon } from "lucide-react";
import {
  Apple,
  Beef,
  CakeSlice,
  Clock3,
  Coffee,
  CupSoda,
  Egg,
  Milk,
  ShoppingBasket,
  Sparkles,
  SprayCan,
  Wheat,
} from "lucide-react";
import type { Schemas } from "@/api/client";
import { Badge, cn } from "@/components/ui";
import { ago, ageDays, money, unitPrice } from "@/lib/format";
import { CONFIDENCE, PRICE_KIND, TARGET_STATUS } from "@/lib/labels";

const CATEGORY_ART: Record<string, { icon: LucideIcon; bg: string; fg: string }> = {
  "Grãos e cereais": { icon: Wheat, bg: "#F6EEDF", fg: "#8C6A2A" },
  "Ovos e frios": { icon: Egg, bg: "#FBF0DA", fg: "#B7791F" },
  Carnes: { icon: Beef, bg: "#FBE4DD", fg: "#B23A30" },
  "Café e chás": { icon: Coffee, bg: "#EFE3D6", fg: "#6B4226" },
  Hortifrúti: { icon: Apple, bg: "#E8F3E3", fg: "#3F7A34" },
  Laticínios: { icon: Milk, bg: "#E9F0F8", fg: "#2B5A8C" },
  Bebidas: { icon: CupSoda, bg: "#E6F4F4", fg: "#1D6F72" },
  Limpeza: { icon: SprayCan, bg: "#EDEBF7", fg: "#4B4A8C" },
  Higiene: { icon: Sparkles, bg: "#F6EAF2", fg: "#8A3F6E" },
  Padaria: { icon: CakeSlice, bg: "#FBEEDD", fg: "#9A5B1E" },
};

export function CategoryArt({ category, className }: { category?: string | null; className?: string }) {
  const art = (category && CATEGORY_ART[category]) || { icon: ShoppingBasket, bg: "#F2EEE6", fg: "#636A65" };
  const Icon = art.icon;
  return (
    <div aria-hidden className={cn("grid size-full place-content-center rounded-[inherit]", className)} style={{ background: art.bg, color: art.fg }}>
      <Icon className="size-[42%] min-h-5 min-w-5" strokeWidth={1.6} />
    </div>
  );
}

export function ProductImage({ image, category, name, className }: { image?: Schemas["ImageRef"] | null; category?: string | null; name: string; className?: string }) {
  return (
    <div className={cn("relative aspect-square overflow-hidden rounded-lg bg-surface-2", className)}>
      {image ? (
        <img src={image.url} alt={image.alt_text ?? name} loading="lazy" decoding="async" className="size-full object-cover" />
      ) : (
        <CategoryArt category={category} />
      )}
    </div>
  );
}

const KNOWN_MARKETS = new Set(["angeloni", "bistek", "fort", "imperatriz"]);

/** Market identity colour: CSS token (with a validated dark step) when known. */
export function marketColor(slug: string | null | undefined, fallback?: string | null): string {
  if (slug && KNOWN_MARKETS.has(slug)) return `var(--color-market-${slug})`;
  return fallback ?? "var(--color-ink-3)";
}

export function MarketDot({ color, className }: { color?: string | null; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2.5 shrink-0 rounded-full ring-2 ring-surface", className)} style={{ background: color ?? "var(--color-ink-3)" }} />;
}

export function MarketName({ market, store, color, className }: { market: string; store?: string | null; color?: string | null; className?: string }) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)}>
      <MarketDot color={color} />
      <span className="truncate">
        <span className="font-semibold">{market}</span>
        {store ? <span className="text-ink-3"> · {store}</span> : null}
      </span>
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const meta = TARGET_STATUS[status] ?? { label: status, tone: "neutral" as const, icon: Clock3, help: "" };
  return (
    <span title={meta.help}>
      <Badge tone={meta.tone} icon={meta.icon} spin={status === "running"}>
        {meta.label}
      </Badge>
    </span>
  );
}

export function FreshnessBadge({ observedAt, freshnessDays }: { observedAt?: string | null; freshnessDays: number }) {
  const days = ageDays(observedAt);
  if (days === null) return <Badge tone="neutral">Sem preço</Badge>;
  const stale = days > freshnessDays;
  return (
    <Badge tone={stale ? "warn" : days < 1 ? "brand" : "neutral"} icon={Clock3}>
      {stale ? `Desatualizado · ${ago(observedAt)}` : days < 1 ? `Hoje · ${ago(observedAt)}` : ago(observedAt)}
    </Badge>
  );
}

export function CoverageMeter({ covered, total, className }: { covered: number; total: number; className?: string }) {
  const complete = total > 0 && covered === total;
  return (
    <div className={cn("space-y-1.5", className)}>
      <p className="text-sm">
        <span className="font-bold tabular text-ink">{covered}</span>
        <span className="text-ink-3"> de {total} itens encontrados</span>
      </p>
      <div className="flex h-2 gap-0.5" role="img" aria-label={`${covered} de ${total} itens encontrados`}>
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={cn("h-full flex-1 rounded-full", i < covered ? (complete ? "bg-brand" : "bg-accent") : "bg-surface-3")} />
        ))}
      </div>
    </div>
  );
}

export function ConfidenceBadge({ level }: { level: string }) {
  const meta = CONFIDENCE[level] ?? { label: level, tone: "neutral" as const };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function PriceKindBadge({ kind }: { kind: string }) {
  if (kind === "regular") return null;
  const meta = PRICE_KIND[kind] ?? { label: kind, tone: "neutral" as const };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function OfferDetails({ offer }: { offer: Schemas["OfferOut"] }) {
  const selling = offer.promo_price ?? offer.regular_price;
  return (
    <div className="space-y-1 text-sm">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-bold tabular">{money(selling)}</span>
        {offer.promo_price ? <span className="text-ink-3 line-through tabular">{money(offer.regular_price)}</span> : null}
        {offer.unit_price ? <span className="text-ink-3 tabular">({unitPrice(offer.unit_price, offer.unit_price_unit)})</span> : null}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {offer.promo_price ? <Badge tone="accent">Promoção</Badge> : null}
        {offer.club_price ? <Badge tone="info">{`${offer.club_label ?? "Clube"}: ${money(offer.club_price)}`}</Badge> : null}
        {offer.quantity_min && offer.quantity_price ? (
          <Badge tone="accent">
            {offer.quantity_mode === "per_group" ? `Levando ${offer.quantity_min}: ${money(offer.quantity_price)} cada` : `A partir de ${offer.quantity_min}: ${money(offer.quantity_price)} cada`}
          </Badge>
        ) : null}
        {offer.extra_prices.map((extra, i) => (
          <Badge key={i} tone="neutral">{`${String(extra.label ?? "Condição")}: ${money(String(extra.price ?? ""))}`}</Badge>
        ))}
      </div>
    </div>
  );
}

export function BigMoney({ value, className, label }: { value: string | number | null | undefined; className?: string; label?: string }) {
  return (
    <span className={cn("font-display font-bold tracking-tight tabular", className)} aria-label={label ? `${label}: ${money(value)}` : undefined}>
      {money(value)}
    </span>
  );
}
