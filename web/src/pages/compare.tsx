import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, Check, ExternalLink, HelpCircle, Route, Search, Sparkles, ThumbsDown, Trophy, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { type ComparisonParams, useComparison, useMarkets, useProfile } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { CoverageMeter, MarketDot, OfferDetails, PriceKindBadge, ProductImage } from "@/components/domain";
import { marketColor } from "@/lib/markets";
import { RecommendationCard } from "@/components/recommendation";
import { Badge, Button, Card, Dialog, EmptyState, ErrorState, InlineAlert, LoadingBlock, Select, Spinner, Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { buttonClass, cn } from "@/components/ui/utils";
import { ago, km, money, quantity, unitPrice } from "@/lib/format";
import { CELL_STATUS, METHOD, TARGET_STATUS, explainReason } from "@/lib/labels";

type Comparison = Schemas["ComparisonOut"];

function useStoreIndex(comparison: Comparison | undefined) {
  return useMemo(() => Object.fromEntries((comparison?.stores ?? []).map((s) => [s.store_id, s])), [comparison]);
}

function StoreTitle({ store, color }: { store?: Schemas["ComparisonStoreOut"]; color?: string | null }) {
  if (!store) return null;
  return (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2 align-middle">
      <MarketDot color={color} />
      <span className="min-w-0 truncate">
        <span className="font-semibold">{store.market_name}</span> <span className="text-ink-3">{store.store_name}</span>
      </span>
    </span>
  );
}

function TravelLine({ travel }: { travel?: Schemas["TravelOut"] | null }) {
  if (!travel) return <span className="text-ink-3">sem deslocamento</span>;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Car aria-hidden className="size-4 text-ink-3" />
      {money(travel.total)} <span className="text-ink-3">({km(travel.distance_km)})</span>
    </span>
  );
}

function CandidatesDialog({ productId, storeId, productName, open, onOpenChange }: { productId: string; storeId: string; productName: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const client = useQueryClient();
  const candidates = useQuery({
    queryKey: ["candidates", productId, storeId],
    enabled: open,
    queryFn: () => unwrap(api.GET("/api/v1/products/{product_id}/candidates", { params: { path: { product_id: productId }, query: { store_id: storeId } } })),
  });
  async function pin(candidateId: string, decision: "accept" | "reject") {
    try {
      await unwrap(api.POST("/api/v1/products/{product_id}/pins", { params: { path: { product_id: productId } }, body: { candidate_id: candidateId, decision } }));
      toast.success(decision === "accept" ? "Anotado: este é o produto certo nesta loja." : "Anotado: este anúncio não será mais usado.");
      void client.invalidateQueries({ queryKey: ["candidates", productId, storeId] });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange} size="lg" title={`Por que este produto?`} description={`Anúncios encontrados para “${productName}” na última busca. As regras decidem a equivalência; você pode confirmar ou rejeitar um anúncio para as próximas buscas.`}>
      {candidates.isLoading ? <Spinner /> : null}
      {candidates.data && !candidates.data.length ? <p className="text-sm text-ink-3">Nenhum anúncio registrado para esta loja ainda.</p> : null}
      <ul className="space-y-3">
        {(candidates.data ?? []).map((c) => (
          <li key={c.id} className={cn("rounded-xl p-3 ring-1", c.chosen ? "bg-brand-soft/60 ring-brand/30" : "ring-line")}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold">{c.title}</p>
                <p className="text-sm text-ink-3">
                  {money(c.promo_price ?? c.regular_price)} {c.unit_price ? `· ${unitPrice(c.unit_price, c.unit_price_unit)}` : ""} · {METHOD[c.method] ?? c.method}
                </p>
              </div>
              {c.chosen ? <Badge tone="brand" icon={Trophy}>Escolhido</Badge> : c.accepted ? <Badge tone="info" icon={Check}>Equivalente</Badge> : <Badge tone="neutral" icon={X}>Descartado</Badge>}
            </div>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {c.reasons.map((reason) => (
                <li key={reason}>
                  <Badge tone={reason.startsWith("missing") || reason.startsWith("excluded") || reason.includes("mismatch") || reason.startsWith("not_main") ? "warn" : "neutral"}>{explainReason(reason)}</Badge>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap gap-2">
              {c.url ? (
                <a href={c.url} target="_blank" rel="noopener noreferrer" className={buttonClass({ variant: "ghost", size: "sm" })}>
                  <ExternalLink aria-hidden className="size-4" /> Ver no site
                </a>
              ) : null}
              <Button variant="ghost" size="sm" onClick={() => void pin(c.id, "accept")}>
                <Check aria-hidden className="size-4" /> É este
              </Button>
              <Button variant="ghost" size="sm" onClick={() => void pin(c.id, "reject")}>
                <ThumbsDown aria-hidden className="size-4" /> Não é este
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}

function Cell({ item, storeId, cell, best, onExplain }: { item: Schemas["ComparisonItemOut"]; storeId: string; cell: Schemas["CellOut"]; best: boolean; onExplain: () => void }) {
  const status = CELL_STATUS[cell.status] ?? { label: cell.status, tone: "neutral" as const };
  const search = cell.last_search ? TARGET_STATUS[cell.last_search.status] : undefined;
  if (!cell.line && !cell.offer) {
    // Say *why* there is no price: not found, blocked, timeout... never a silent blank.
    return (
      <div className="space-y-1 p-1 text-sm text-ink-3">
        <Badge tone={search?.tone ?? status.tone} icon={search?.icon}>{search?.label ?? status.label}</Badge>
        <p className="text-xs">
          {search && cell.last_search?.status !== "not_found" ? `${search.help} ` : ""}
          {cell.last_search ? `Última busca ${ago(cell.last_search.finished_at)}.` : "Ainda não buscado nesta loja."}
        </p>
      </div>
    );
  }
  const newerFailure =
    search && cell.offer && cell.last_search && !["found", "unavailable", "no_price"].includes(cell.last_search.status) && (cell.last_search.finished_at ?? "") > cell.offer.observed_at;
  return (
    <div className={cn("space-y-1.5 rounded-lg p-2.5", best && "bg-accent-soft/70 ring-1 ring-accent/30")}>
      <div className="flex flex-wrap items-center gap-1.5">
        {cell.line ? <span className="text-base font-bold tabular">{money(cell.line.cost)}</span> : null}
        {best ? <Badge tone="accent" icon={Trophy}>Melhor preço</Badge> : null}
        {cell.status !== "ok" ? <Badge tone={status.tone}>{status.label}</Badge> : null}
        {cell.line ? <PriceKindBadge kind={cell.line.price_kind} /> : null}
      </div>
      {cell.line ? (
        <p className="text-xs text-ink-3">
          {unitPrice(cell.line.unit_price, cell.line.unit_price_unit)}
          {cell.line.approximate ? " · estimado" : ""}
          {cell.line.notes.length ? ` · ${cell.line.notes.join("; ")}` : ""}
        </p>
      ) : null}
      {cell.offer ? (
        <p className="line-clamp-2 text-xs text-ink-2">
          {cell.offer.title} · {ago(cell.offer.observed_at)}
        </p>
      ) : null}
      {cell.reason && cell.status !== "ok" ? <p className="text-xs text-ink-3">{cell.reason}</p> : null}
      {newerFailure ? <p className="text-xs font-medium text-warn">Última busca: {search.label.toLowerCase()} ({ago(cell.last_search!.finished_at)}); mostrando o preço anterior.</p> : null}
      <div className="flex flex-wrap gap-x-3">
        {cell.offer?.url ? (
          <a href={cell.offer.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline">
            Oferta <ExternalLink aria-hidden className="size-3" />
          </a>
        ) : null}
        <button type="button" onClick={onExplain} className="inline-flex items-center gap-1 text-xs font-semibold text-ink-2 hover:text-ink hover:underline">
          <HelpCircle aria-hidden className="size-3" /> Por quê?
        </button>
      </div>
      <span className="sr-only">
        {item.name} em {storeId}
      </span>
    </div>
  );
}

function ItemsBreakdown({ comparison, colors }: { comparison: Comparison; colors: Record<string, string | null | undefined> }) {
  const stores = comparison.stores;
  const [explain, setExplain] = useState<{ productId: string; storeId: string; name: string } | null>(null);
  return (
    <section aria-labelledby="item-a-item" className="space-y-3">
      <h2 id="item-a-item" className="text-xl font-semibold">Item por item</h2>
      <div className="hidden overflow-x-auto rounded-xl border border-line bg-surface shadow-card lg:block">
        <table className="w-full min-w-[720px] table-fixed border-collapse text-left">
          <caption className="sr-only">Custo de cada item da lista em cada loja</caption>
          <thead>
            <tr className="border-b border-line bg-surface-2 text-sm">
              <th scope="col" className="w-52 px-4 py-3 font-semibold">Produto</th>
              {stores.map((s) => (
                <th key={s.store_id} scope="col" className="px-3 py-3 font-semibold">
                  <StoreTitle store={s} color={colors[s.market_slug]} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparison.items.map((item) => (
              <tr key={item.item_id} className="border-b border-line align-top last:border-0">
                <th scope="row" className="px-4 py-3 font-normal">
                  <div className="flex items-center gap-3">
                    <ProductImage image={item.image_id ? { id: item.image_id, url: `/api/v1/images/${item.image_id}`, source: "seed" } : null} category={item.category} name={item.name} className="size-12 shrink-0" />
                    <span>
                      <span className="block font-semibold">{item.name}</span>
                      <span className="text-sm text-ink-3">{quantity(item.quantity, item.unit)}</span>
                    </span>
                  </div>
                </th>
                {stores.map((s) => (
                  <td key={s.store_id} className="px-2 py-2">
                    <Cell item={item} storeId={s.store_name} cell={item.cells[s.store_id]!} best={item.best_store_id === s.store_id && stores.length > 1} onExplain={() => setExplain({ productId: item.product_id, storeId: s.store_id, name: item.name })} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="space-y-3 lg:hidden">
        {comparison.items.map((item) => (
          <li key={item.item_id}>
            <Card className="p-3">
              <div className="mb-2 flex items-center gap-3">
                <ProductImage image={item.image_id ? { id: item.image_id, url: `/api/v1/images/${item.image_id}`, source: "seed" } : null} category={item.category} name={item.name} className="size-12 shrink-0" />
                <div>
                  <p className="font-semibold">{item.name}</p>
                  <p className="text-sm text-ink-3">{quantity(item.quantity, item.unit)}</p>
                </div>
              </div>
              <ul className="divide-y divide-line">
                {stores.map((s) => (
                  <li key={s.store_id} className="py-2">
                    <p className="mb-1 text-sm">
                      <StoreTitle store={s} color={colors[s.market_slug]} />
                    </p>
                    <Cell item={item} storeId={s.store_name} cell={item.cells[s.store_id]!} best={item.best_store_id === s.store_id && stores.length > 1} onExplain={() => setExplain({ productId: item.product_id, storeId: s.store_id, name: item.name })} />
                  </li>
                ))}
              </ul>
            </Card>
          </li>
        ))}
      </ul>
      {explain ? <CandidatesDialog productId={explain.productId} storeId={explain.storeId} productName={explain.name} open onOpenChange={(open) => !open && setExplain(null)} /> : null}
    </section>
  );
}

function PlanView({ comparison, colors }: { comparison: Comparison; colors: Record<string, string | null | undefined> }) {
  const index = useStoreIndex(comparison);
  const items = Object.fromEntries(comparison.items.map((i) => [i.item_id, i]));
  const plan = comparison.plan.best;
  if (!plan) return <p className="text-sm text-ink-3">Sem preços suficientes para montar um plano.</p>;
  return (
    <div className="space-y-4">
      <ol className="grid gap-3 md:grid-cols-2">
        {plan.stops.map((stop, i) => (
          <li key={stop.store_id} className="min-w-0">
            <Card className="h-full min-w-0 p-4">
              <p className="text-xs font-semibold tracking-wide text-ink-3 uppercase">{plan.stops.length > 1 ? `Parada ${i + 1}` : "Loja"}</p>
              <p className="mt-1 flex min-w-0 text-lg">
                <StoreTitle store={index[stop.store_id]} color={colors[index[stop.store_id]?.market_slug ?? ""]} />
              </p>
              <ul className="mt-3 space-y-1 text-sm">
                {stop.item_ids.map((id) => (
                  <li key={id} className="flex justify-between gap-3">
                    <span className="min-w-0 truncate">{items[id]?.name}</span>
                    <span className="shrink-0 tabular text-ink-2">{money(items[id]?.cells[stop.store_id]?.line?.cost)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex justify-between border-t border-line pt-2 font-semibold">
                <span>Subtotal</span>
                <span className="tabular">{money(stop.products_total)}</span>
              </p>
            </Card>
          </li>
        ))}
      </ol>
      {plan.travel ? (
        <Card className="flex flex-wrap items-center gap-3 p-4 text-sm">
          <Route aria-hidden className="size-5 text-brand" />
          <span className="font-semibold">Rota: </span>
          <span>{plan.travel.route.map((r) => (r === "home" ? "Casa" : `${index[r]?.market_name ?? ""} ${index[r]?.store_name ?? ""}`)).join(" → ")}</span>
          <span className="w-full text-ink-3">{plan.travel.formula}</span>
        </Card>
      ) : null}
      {comparison.plan.alternatives.length ? (
        <div>
          <h3 className="mb-2 font-semibold">Outras opções consideradas</h3>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface text-sm">
            {comparison.plan.alternatives.map((alt, i) => (
              <li key={i} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
                <span className="min-w-0">
                  {alt.stops.map((s) => `${index[s.store_id]?.market_name} ${index[s.store_id]?.store_name}`).join(" + ")}
                  <span className="text-ink-3"> · {alt.covered} de {comparison.items.length} itens</span>
                </span>
                <span className="font-semibold tabular">{money(alt.effective_total)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function CommonBasketView({ comparison, colors }: { comparison: Comparison; colors: Record<string, string | null | undefined> }) {
  const index = useStoreIndex(comparison);
  const common = comparison.common;
  const names = Object.fromEntries(comparison.items.map((i) => [i.item_id, i.name]));
  return (
    <div className="space-y-3">
      <InlineAlert tone={common.item_ids.length ? "info" : "warn"}>{common.note}</InlineAlert>
      {common.item_ids.length ? (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[520px] text-left text-sm">
            <caption className="sr-only">Totais da cesta comum por loja</caption>
            <thead className="bg-surface-2">
              <tr>
                <th scope="col" className="px-4 py-2.5">Loja</th>
                <th scope="col" className="px-4 py-2.5 text-right">Produtos</th>
                <th scope="col" className="px-4 py-2.5 text-right">Deslocamento</th>
                <th scope="col" className="px-4 py-2.5 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {[...common.stores]
                .sort((a, b) => Number(a.effective_total) - Number(b.effective_total))
                .map((row) => (
                  <tr key={row.store_id} className={cn("border-t border-line", common.winner_store_id === row.store_id && "bg-brand-soft/50")}>
                    <th scope="row" className="px-4 py-2.5 font-normal">
                      <span className="inline-flex items-center gap-2">
                        <StoreTitle store={index[row.store_id]} color={colors[index[row.store_id]?.market_slug ?? ""]} />
                        {common.winner_store_id === row.store_id ? <Badge tone="brand" icon={Trophy}>Menor total</Badge> : null}
                      </span>
                    </th>
                    <td className="px-4 py-2.5 text-right tabular">{money(row.products_total)}</td>
                    <td className="px-4 py-2.5 text-right tabular">{row.travel ? money(row.travel.total) : "—"}</td>
                    <td className="px-4 py-2.5 text-right font-bold tabular">{money(row.effective_total)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {common.excluded_item_ids.length ? (
        <p className="text-sm text-ink-3">Fora da cesta comum (não encontrados em todas as lojas): {common.excluded_item_ids.map((id) => names[id]).join(", ")}.</p>
      ) : null}
    </div>
  );
}

function CoverageView({ comparison, colors }: { comparison: Comparison; colors: Record<string, string | null | undefined> }) {
  const index = useStoreIndex(comparison);
  const names = Object.fromEntries(comparison.items.map((i) => [i.item_id, i.name]));
  const max = comparison.coverage.max_coverage;
  return (
    <div className="space-y-3">
      <InlineAlert tone="info">{comparison.coverage.note}</InlineAlert>
      <ul className="grid gap-3 md:grid-cols-2">
        {comparison.coverage.stores.map((row) => {
          const leader = comparison.coverage.best_store_id === row.store_id;
          const partial = row.covered < max;
          return (
            <li key={row.store_id} className="min-w-0">
              <Card className={cn("h-full min-w-0 space-y-3 p-4", leader && "ring-2 ring-brand/40")}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <StoreTitle store={index[row.store_id]} color={colors[index[row.store_id]?.market_slug ?? ""]} />
                  {leader ? <Badge tone="brand" icon={Trophy}>Melhor entre as mais completas</Badge> : partial ? <Badge tone="warn">Total não comparável</Badge> : null}
                </div>
                <CoverageMeter covered={row.covered} total={row.total_items} />
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <p className="text-xs text-ink-3">Total dos {row.covered} itens encontrados</p>
                    <p className="font-display text-2xl font-bold tabular">{money(row.products_total)}</p>
                  </div>
                  <p className="text-right text-sm">
                    <TravelLine travel={row.travel} />
                  </p>
                </div>
                {row.missing_item_ids.length ? <p className="text-sm text-ink-3">Faltam: {row.missing_item_ids.map((id) => names[id]).join(", ")}</p> : null}
                {row.stale_used ? <p className="text-sm text-warn">{row.stale_used} preço(s) desatualizado(s) incluído(s) com sua autorização.</p> : null}
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ComparePage() {
  const profile = useProfile();
  const [params, setParams] = useState<ComparisonParams>({});
  const comparison = useComparison(params);
  const markets = useMarkets();
  const colors = useMemo(() => Object.fromEntries((markets.data ?? []).map((m) => [m.slug, marketColor(m.slug, m.brand_color)])), [markets.data]);

  if (comparison.isLoading) return <LoadingBlock label="Calculando onde compensa" rows={3} />;
  if (comparison.error || !comparison.data) return <ErrorState error={errorMessage(comparison.error)} onRetry={() => void comparison.refetch()} />;
  const data = comparison.data;
  const hasStale = data.items.some((i) => Object.values(i.cells).some((c) => c.status === "stale"));
  const noStores = !data.stores.length;
  const noItems = !data.items.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Veja onde compensa"
        description="Produtos, deslocamento e total separados. Cesta incompleta nunca é somada em silêncio."
        actions={
          <Link to="/buscar" className={buttonClass({ variant: "secondary" })}>
            <Search aria-hidden className="size-4" /> Atualizar preços
          </Link>
        }
      />
      {noItems || noStores ? (
        <EmptyState icon={Sparkles} title={noItems ? "Monte sua lista primeiro" : "Escolha as lojas"} action={<Link className={buttonClass()} to={noItems ? "/lista" : "/mercados"}>{noItems ? "Montar lista" : "Escolher mercados"}</Link>}>
          A comparação aparece depois que houver produtos, lojas e uma busca de preços.
        </EmptyState>
      ) : (
        <>
          <Card className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
            <label className="flex items-center gap-2 text-sm font-semibold">
              <Switch checked={params.include_travel ?? profile.data?.include_travel_cost ?? true} onCheckedChange={(v) => setParams((p) => ({ ...p, include_travel: v }))} aria-label="Incluir deslocamento" />
              Incluir deslocamento
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold">
              Máx. de paradas
              <Select className="h-9 w-20 rounded-full py-0 pl-3 text-sm" value={String(params.max_stops ?? data.max_stops)} onChange={(e) => setParams((p) => ({ ...p, max_stops: Number(e.target.value) }))}>
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
              </Select>
            </label>
            {hasStale || params.allow_stale ? (
              <label className="flex items-center gap-2 text-sm font-semibold">
                <Switch checked={Boolean(params.allow_stale)} onCheckedChange={(v) => setParams((p) => ({ ...p, allow_stale: v }))} aria-label="Usar preços desatualizados" />
                Usar preços com mais de {data.freshness_days} dias
              </label>
            ) : null}
            {comparison.isFetching ? <Spinner label="Recalculando" /> : null}
          </Card>
          {data.include_travel && (!data.home_located || !data.vehicle_configured) ? (
            <InlineAlert tone="info" title="Deslocamento ainda não incluído" action={<Link to="/perfil#endereco" className={buttonClass({ variant: "secondary", size: "sm" })}>Configurar</Link>}>
              {!data.home_located ? "Cadastre seu endereço com localização" : "Cadastre seu veículo"} para somar o custo de ida e volta.
            </InlineAlert>
          ) : null}
          {params.allow_stale ? <InlineAlert tone="warn">Você autorizou o uso de preços antigos: eles podem não refletir o preço atual e reduzem a confiança da recomendação.</InlineAlert> : null}
          {data.recommendation.kind === "none" ? (
            <EmptyState icon={Search} title="Ainda sem preços suficientes" action={<Link className={buttonClass()} to="/buscar">Buscar preços</Link>}>
              {data.recommendation.warnings.join(" ") || "Faça uma busca para ver a recomendação."}
            </EmptyState>
          ) : (
            <RecommendationCard comparison={data} colors={colors} />
          )}
          <Tabs defaultValue="plano" className="space-y-4">
            <TabsList aria-label="Visões da comparação" className="w-fit max-w-full">
              <TabsTrigger value="plano">Plano econômico</TabsTrigger>
              <TabsTrigger value="comum">Cesta comum</TabsTrigger>
              <TabsTrigger value="mercados">Por mercado</TabsTrigger>
            </TabsList>
            <TabsContent value="plano">
              <PlanView comparison={data} colors={colors} />
            </TabsContent>
            <TabsContent value="comum">
              <CommonBasketView comparison={data} colors={colors} />
            </TabsContent>
            <TabsContent value="mercados">
              <CoverageView comparison={data} colors={colors} />
            </TabsContent>
          </Tabs>
          <ItemsBreakdown comparison={data} colors={colors} />
          <details className="rounded-xl border border-line bg-surface px-4 py-3 text-sm">
            <summary className="cursor-pointer font-semibold">Detalhes das ofertas</summary>
            <ul className="mt-3 space-y-3">
              {data.items.flatMap((item) =>
                Object.entries(item.cells)
                  .filter(([, c]) => c.offer)
                  .map(([storeId, c]) => (
                    <li key={`${item.item_id}-${storeId}`} className="rounded-lg bg-surface-2 p-3">
                      <p className="mb-1 font-semibold">
                        {item.name} — {data.stores.find((s) => s.store_id === storeId)?.market_name}
                      </p>
                      <OfferDetails offer={c.offer!} />
                      <p className="mt-1 text-xs text-ink-3">
                        {METHOD[c.offer!.method] ?? c.offer!.method} · observado {ago(c.offer!.observed_at)}
                        {c.offer!.outlier_reason ? ` · ${c.offer!.outlier_reason}` : ""}
                      </p>
                    </li>
                  )),
              )}
            </ul>
          </details>
        </>
      )}
    </div>
  );
}
