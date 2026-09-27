import { ArrowRight, ChevronDown, Info, MapPin, Store as StoreIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import type { Schemas } from "@/api/client";
import { useAddresses, useMarkets, useSaveStores } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { MarketDot, marketColor } from "@/components/domain";
import { Badge, Button, buttonClass, Card, Checkbox, cn, ErrorState, InlineAlert, Input, LoadingBlock } from "@/components/ui";
import { ago, km, pluralize } from "@/lib/format";
import { HEALTH } from "@/lib/labels";

type Selection = Record<string, { selected: boolean; toll: string }>;

function StoreRow({ store, state, onToggle, onToll }: { store: Schemas["StoreOut"]; state: { selected: boolean; toll: string }; onToggle: (value: boolean) => void; onToll: (value: string) => void }) {
  const id = `store-${store.id}`;
  return (
    <li className={cn("rounded-lg px-3 py-2.5 transition-colors", state.selected ? "bg-brand-soft/60" : "hover:bg-surface-2")}>
      <div className="flex items-center gap-3">
        <Checkbox id={id} checked={state.selected} onCheckedChange={(v) => onToggle(v === true)} />
        <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer">
          <span className="block truncate font-semibold">{store.name}</span>
          <span className="block truncate text-sm text-ink-3">
            {[store.district, store.city].filter(Boolean).join(" · ")}
            {store.last_observed_at ? ` · preços ${ago(store.last_observed_at)}` : ""}
          </span>
        </label>
        {store.distance_km ? (
          <span className="shrink-0 text-sm font-semibold text-ink-2 tabular">{km(store.distance_km)}</span>
        ) : store.latitude === null ? (
          <span className="shrink-0 text-xs text-ink-3">sem localização</span>
        ) : null}
      </div>
      {state.selected ? (
        <div className="mt-2 flex items-center gap-2 pl-8">
          <label htmlFor={`${id}-toll`} className="text-xs text-ink-3">
            Pedágio ida e volta (R$)
          </label>
          <Input id={`${id}-toll`} inputMode="decimal" className="h-8 w-24 rounded-full text-sm" value={state.toll} onChange={(e) => onToll(e.target.value)} placeholder="0,00" />
        </div>
      ) : null}
    </li>
  );
}

function MarketCard({ market, selection, setSelection }: { market: Schemas["MarketOut"]; selection: Selection; setSelection: (updater: (s: Selection) => Selection) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const health = HEALTH[market.health] ?? HEALTH.sem_dados!;
  const selectedCount = market.stores.filter((s) => selection[s.id]?.selected).length;
  const visible = expanded ? market.stores : market.stores.slice(0, 5);
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-4 sm:px-5">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-content-center rounded-xl text-white" style={{ background: marketColor(market.slug, market.brand_color) }}>
            <StoreIcon aria-hidden className="size-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold">{market.name}</h2>
            <p className="text-sm text-ink-3">
              {pluralize(market.stores.length, "loja", "lojas")}
              {selectedCount ? ` · ${selectedCount} selecionada${selectedCount > 1 ? "s" : ""}` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge tone={health.tone}>{health.label}</Badge>
          {market.last_success_at ? <span className="text-xs text-ink-3">último sucesso {ago(market.last_success_at)}</span> : null}
        </div>
      </div>
      {market.stores[0]?.price_scope_note ? (
        <p className="flex gap-2 bg-surface-2 px-4 py-2.5 text-sm text-ink-2 sm:px-5">
          <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-info" />
          {market.stores[0].price_scope_note}
        </p>
      ) : null}
      <ul className="space-y-0.5 p-2 sm:p-3">
        {visible.map((store) => (
          <StoreRow
            key={store.id}
            store={store}
            state={selection[store.id] ?? { selected: false, toll: "" }}
            onToggle={(value) => setSelection((s) => ({ ...s, [store.id]: { selected: value, toll: s[store.id]?.toll ?? "" } }))}
            onToll={(value) => setSelection((s) => ({ ...s, [store.id]: { selected: true, toll: value } }))}
          />
        ))}
      </ul>
      <div className="flex flex-wrap gap-2 border-t border-line px-4 py-2.5 sm:px-5">
        {market.stores.length > 5 ? (
          <Button variant="ghost" size="sm" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
            {expanded ? "Mostrar menos" : `Ver todas as ${market.stores.length} lojas`}
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={() => setShowNotes((v) => !v)} aria-expanded={showNotes}>
          Como os preços são obtidos <ChevronDown aria-hidden className={cn("size-4 transition-transform", showNotes && "rotate-180")} />
        </Button>
      </div>
      {showNotes && market.notes ? <p className="px-4 pb-4 text-sm text-ink-2 sm:px-5">{market.notes}</p> : null}
    </Card>
  );
}

export function MarketsPage() {
  const markets = useMarkets();
  const addresses = useAddresses();
  const save = useSaveStores();
  const navigate = useNavigate();
  const [selection, setSelection] = useState<Selection>({});

  const initial = useMemo(() => {
    const state: Selection = {};
    for (const market of markets.data ?? []) for (const store of market.stores) state[store.id] = { selected: store.selected ?? false, toll: Number(store.toll_round_trip) ? String(store.toll_round_trip) : "" };
    return state;
  }, [markets.data]);
  useEffect(() => setSelection(initial), [initial]);

  if (markets.isLoading) return <LoadingBlock label="Carregando mercados" rows={4} />;
  if (markets.error || !markets.data) return <ErrorState error="Não foi possível carregar os mercados." onRetry={() => void markets.refetch()} />;

  const selectedIds = Object.entries(selection).filter(([, v]) => v.selected);
  const dirty = JSON.stringify(selection) !== JSON.stringify(initial);
  const hasHome = (addresses.data ?? []).some((a) => a.latitude !== null && a.latitude !== undefined);

  async function persist(goSearch: boolean) {
    await save.mutateAsync(selectedIds.map(([store_id, v]) => ({ store_id, toll_round_trip: v.toll ? v.toll.replace(",", ".") : "0" })));
    if (goSearch) navigate("/buscar");
  }

  return (
    <div className="pb-20">
      <PageHeader title="Escolha onde comparar" description="Selecione as lojas em que você realmente compraria. Cada mercado coleta os preços de um jeito, sempre respeitando as regras de acesso do site." />
      {!hasHome ? (
        <div className="mb-5">
          <InlineAlert tone="info" title="Cadastre seu endereço para ordenar por distância" action={<Link to="/perfil#endereco" className={buttonClass({ variant: "secondary", size: "sm" })}><MapPin aria-hidden className="size-4" /> Adicionar endereço</Link>}>
            Com endereço e veículo, a comparação inclui o custo de ida e volta.
          </InlineAlert>
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        {markets.data.map((market) => (
          <MarketCard key={market.id} market={market} selection={selection} setSelection={setSelection} />
        ))}
      </div>
      <div className="fixed inset-x-4 bottom-24 z-30 lg:sticky lg:inset-x-auto lg:bottom-6 lg:mt-6">
        <Card className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 shadow-lift">
          <p className="text-sm">
            <span className="font-bold">{pluralize(selectedIds.length, "loja selecionada", "lojas selecionadas")}</span>
            {dirty ? <span className="text-ink-3"> · alterações não salvas</span> : null}
          </p>
          <div className="flex gap-2">
            {dirty ? (
              <Button variant="secondary" size="sm" loading={save.isPending} onClick={() => void persist(false)}>
                Salvar
              </Button>
            ) : null}
            <Button size="sm" disabled={!selectedIds.length} loading={save.isPending} onClick={() => void persist(true)}>
              Buscar preços <ArrowRight aria-hidden className="size-4" />
            </Button>
          </div>
        </Card>
      </div>
      <p className="mt-6 flex items-center gap-2 text-xs text-ink-3">
        <MarketDot color="var(--color-brand)" /> As cores dos mercados são só identificação; o nome está sempre escrito.
      </p>
    </div>
  );
}
