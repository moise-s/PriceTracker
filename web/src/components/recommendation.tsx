import { AlertTriangle, Car, ChevronDown, Info, MapPin, PiggyBank, ShoppingBag, Sparkles } from "lucide-react";
import { useState } from "react";
import type { Schemas } from "@/api/client";
import { BigMoney, ConfidenceBadge, CoverageMeter, FreshnessBadge, MarketDot } from "@/components/domain";
import { Badge, Card, cn } from "@/components/ui";
import { money } from "@/lib/format";

type Comparison = Schemas["ComparisonOut"];

export function storeLabel(comparison: Comparison, storeId: string): { market: string; store: string; color?: string | null } {
  const store = comparison.stores.find((s) => s.store_id === storeId);
  return { market: store?.market_name ?? "Loja", store: store?.store_name ?? "", color: undefined };
}

export function RecommendationCard({ comparison, colors, compact = false }: { comparison: Comparison; colors: Record<string, string | null | undefined>; compact?: boolean }) {
  const rec = comparison.recommendation;
  const [open, setOpen] = useState(false);
  if (rec.kind === "none") return null;
  const plan = comparison.plan.best;
  const stores = rec.store_ids.map((id) => comparison.stores.find((s) => s.store_id === id)).filter(Boolean) as Schemas["ComparisonStoreOut"][];
  const reference = rec.savings_reference_store_id ? comparison.stores.find((s) => s.store_id === rec.savings_reference_store_id) : undefined;

  return (
    <Card className="relative overflow-hidden border-brand/20 p-0">
      <div aria-hidden className="pointer-events-none absolute -top-24 -right-20 size-72 rounded-full bg-brand-soft/80 blur-2xl" />
      <div className="relative grid gap-6 p-5 sm:p-7 md:grid-cols-[1.4fr_1fr]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand" icon={Sparkles}>
              {rec.kind === "split" ? "Plano dividido" : "Recomendação da semana"}
            </Badge>
            <ConfidenceBadge level={rec.confidence} />
          </div>
          <div>
            <h2 className="text-[26px] leading-tight font-bold sm:text-[32px]">{rec.headline}</h2>
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
              {stores.map((store) => (
                <li key={store.store_id} className="inline-flex items-center gap-2 text-[15px] text-ink-2">
                  <MarketDot color={colors[store.market_slug]} />
                  <span>
                    <span className="font-semibold text-ink">{store.market_name}</span> · {store.store_name}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
            <div>
              <p className="text-sm font-medium text-ink-3">{rec.travel_total ? "Total com deslocamento" : "Total dos produtos"}</p>
              <BigMoney value={rec.effective_total} className="text-5xl text-ink sm:text-[56px]" label="Total" />
            </div>
            {rec.savings && Number(rec.savings) > 0 ? (
              <div className="mb-2 flex items-center gap-2 rounded-2xl bg-accent-soft px-3.5 py-2 text-accent-ink">
                <PiggyBank aria-hidden className="size-5" />
                <span className="text-sm leading-tight">
                  <span className="block font-bold">Economia de {money(rec.savings)}</span>
                  {reference ? <span className="block opacity-90">vs. {reference.market_name} {reference.store_name}</span> : null}
                </span>
              </div>
            ) : null}
          </div>
          <dl className="grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="rounded-xl bg-surface-2 px-3.5 py-3 ring-1 ring-line">
              <dt className="flex items-center gap-1.5 text-xs font-semibold text-ink-3">
                <ShoppingBag aria-hidden className="size-3.5" /> Produtos
              </dt>
              <dd className="mt-0.5 text-lg font-bold tabular">{money(rec.products_total)}</dd>
            </div>
            <div className="rounded-xl bg-surface-2 px-3.5 py-3 ring-1 ring-line">
              <dt className="flex items-center gap-1.5 text-xs font-semibold text-ink-3">
                <Car aria-hidden className="size-3.5" /> Deslocamento
              </dt>
              <dd className="mt-0.5 text-lg font-bold tabular">{rec.travel_total ? money(rec.travel_total) : comparison.include_travel ? "—" : "não incluído"}</dd>
            </div>
          </dl>
        </div>
        <div className="space-y-4 rounded-2xl bg-surface/80 p-4 ring-1 ring-line md:self-start">
          <CoverageMeter covered={rec.covered} total={rec.total_items} />
          <div className="flex flex-wrap gap-2">
            <FreshnessBadge observedAt={rec.oldest_observed_at} freshnessDays={comparison.freshness_days} />
            {plan?.travel ? (
              <Badge tone="neutral" icon={MapPin}>
                {plan.travel.method === "osrm" ? "Rota rodoviária" : "Distância estimada"}
              </Badge>
            ) : null}
          </div>
          {plan?.travel ? <p className="text-xs leading-relaxed text-ink-3">{plan.travel.formula}</p> : null}
          {!compact ? (
            <button type="button" className="flex w-full items-center justify-between rounded-lg px-1 py-1 text-sm font-semibold text-brand hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
              Por que esta recomendação?
              <ChevronDown aria-hidden className={cn("size-4 transition-transform", open && "rotate-180")} />
            </button>
          ) : null}
        </div>
      </div>
      {!compact && open ? (
        <div className="relative space-y-3 border-t border-line bg-surface-2 px-5 py-4 sm:px-7">
          <ul className="space-y-1.5 text-sm text-ink-2">
            {rec.explanation.map((line) => (
              <li key={line} className="flex gap-2">
                <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-brand" />
                {line}
              </li>
            ))}
            {rec.confidence_reasons.map((line) => (
              <li key={line} className="flex gap-2">
                <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-ink-3" />
                {line}
              </li>
            ))}
          </ul>
          <ul className="space-y-1 text-xs text-ink-3">
            {comparison.plan.assumptions.map((line) => (
              <li key={line}>• {line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {rec.warnings.length ? (
        <div className="relative space-y-1.5 border-t border-warn/20 bg-warn-soft px-5 py-3 text-sm text-warn sm:px-7">
          {rec.warnings.map((w) => (
            <p key={w} className="flex gap-2">
              <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
              {w}
            </p>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
