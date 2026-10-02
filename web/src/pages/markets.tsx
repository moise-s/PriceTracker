import { translate, useLocale } from "@/lib/i18n";
import { ChevronDown, Info, MapPin, Search, Store as StoreIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import type { Schemas } from "@/api/client";
import { useActiveRun, useAddresses, useDefaultList, useMarkets, useMe, useSaveStores, useStartRun } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { MarketDot } from "@/components/domain";
import { filterText, marketColor } from "@/lib/markets";
import { Badge, Button, Card, Checkbox, EmptyState, ErrorState, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow } from "@/components/ui";
import { buttonClass, cn } from "@/components/ui/utils";
import { ago, km, pluralize } from "@/lib/format";
import { HEALTH } from "@/lib/labels";

type Selection = Record<string, { selected: boolean; toll: string }>;

function StoreRow({ store, state, onToggle, onToll }: { store: Schemas["StoreOut"]; state: { selected: boolean; toll: string }; onToggle: (value: boolean) => void; onToll: (value: string) => void }) {
  useLocale();
  const id = `store-${store.id}`;
  return (
    <li className={cn("rounded-lg px-3 py-2.5 transition-colors", state.selected ? "bg-brand-soft/60" : "hover:bg-surface-2")}>
      <div className="flex items-center gap-3">
        <Checkbox id={id} checked={state.selected} onCheckedChange={(v) => onToggle(v === true)} />
        <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer">
          <span className="block truncate font-semibold">{store.name}</span>
          <span className="block truncate text-sm text-ink-3">
            {[store.district, [store.city, store.state].filter(Boolean).join("/")].filter(Boolean).join(" · ")}
            {translate(store.last_observed_at ? ` · preços ${ago(store.last_observed_at)}` : "")}
          </span>
        </label>
        {store.distance_km !== null && store.distance_km !== undefined ? (
          <span className="shrink-0 text-sm font-semibold text-ink-2 tabular">{translate(km(store.distance_km))}</span>
        ) : store.latitude === null ? (
          <span className="shrink-0 text-xs text-ink-3">{translate("sem localização")}</span>
        ) : null}
      </div>
      {state.selected ? (
        <div className="mt-2 flex items-center gap-2 pl-8">
          <label htmlFor={`${id}-toll`} className="text-xs text-ink-3">{translate("Pedágio ida e volta (R$)")}</label>
          <Input id={`${id}-toll`} inputMode="decimal" className="h-8 w-24 rounded-full text-sm" value={state.toll} onChange={(e) => onToll(e.target.value)} placeholder={translate("0,00")} />
        </div>
      ) : null}
    </li>
  );
}

function MarketCard({ market, selection, setSelection }: { market: Schemas["MarketOut"]; selection: Selection; setSelection: (updater: (s: Selection) => Selection) => void }) {
  useLocale();
  const [expanded, setExpanded] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const health = HEALTH[market.health] ?? HEALTH.sem_dados!;
  const selectedCount = market.stores.filter((s) => selection[s.id]?.selected).length;
  const visible = expanded ? market.stores : market.stores.slice(0, 5);
  const headingId = `market-${market.id}`;
  return (
    <Card as="section" aria-labelledby={headingId} className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-4 sm:px-5">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-content-center rounded-xl text-white" style={{ background: marketColor(market.slug, market.brand_color) }}>
            <StoreIcon aria-hidden className="size-5" />
          </span>
          <div>
            <h2 id={headingId} className="text-lg font-bold">{market.name}</h2>
            <p className="text-sm text-ink-3">
              {translate(pluralize(market.stores.length, "loja", "lojas"))}
              {translate(selectedCount ? ` · ${selectedCount} selecionada${selectedCount > 1 ? "s" : ""}` : "")}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge tone={health.tone}>{translate(health.label)}</Badge>
          {market.last_success_at ? <span className="text-xs text-ink-3">{translate("último sucesso ")}{translate(ago(market.last_success_at))}</span> : null}
        </div>
      </div>
      {market.stores[0]?.price_scope_note ? (
        <p className="flex gap-2 bg-surface-2 px-4 py-2.5 text-sm text-ink-2 sm:px-5">
          <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-info" />
          {translate(market.stores[0].price_scope_note)}
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
            {translate(expanded ? "Mostrar menos" : `Ver todas as ${market.stores.length} lojas`)}
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={() => setShowNotes((v) => !v)} aria-expanded={showNotes}>{translate("Como os preços são obtidos ")}<ChevronDown aria-hidden className={cn("size-4 transition-transform", showNotes && "rotate-180")} />
        </Button>
      </div>
      {showNotes && market.notes ? <p className="px-4 pb-4 text-sm text-ink-2 sm:px-5">{translate(market.notes)}</p> : null}
    </Card>
  );
}

export function MarketsPage() {
  useLocale();
  const [searchParams] = useSearchParams();
  const priceCheckFlow = searchParams.get("flow") === "price-check";
  const markets = useMarkets();
  const me = useMe();
  const addresses = useAddresses();
  const save = useSaveStores();
  const start = useStartRun();
  const active = useActiveRun();
  const lists = useDefaultList();
  const navigate = useNavigate();
  // Unsaved edits are layered over the saved selection (no effect needed to copy server state).
  const [edits, setEdits] = useState<Selection>({});
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [city, setCity] = useState("");
  const [onlySelected, setOnlySelected] = useState(false);

  const initial = useMemo(() => {
    const state: Selection = {};
    for (const market of markets.data ?? []) for (const store of market.stores) state[store.id] = { selected: store.selected ?? false, toll: Number(store.toll_round_trip) ? String(store.toll_round_trip) : "" };
    return state;
  }, [markets.data]);
  const selection = useMemo(() => ({ ...initial, ...edits }), [initial, edits]);
  const setSelection = (updater: (s: Selection) => Selection) => setEdits(() => updater(selection));

  if (markets.isLoading) return <LoadingBlock label={translate("Carregando mercados")} rows={4} />;
  if (markets.error || !markets.data) return <ErrorState error={translate("Não foi possível carregar os mercados.")} onRetry={() => void markets.refetch()} />;

  const selectedIds = Object.entries(selection).filter(([id, v]) => id in initial && v.selected);
  const dirty = Object.entries(edits).some(([id, value]) => id in initial && JSON.stringify(value) !== JSON.stringify(initial[id]));
  const hasHome = (addresses.data ?? []).some((a) => a.latitude !== null && a.latitude !== undefined);
  const stores = markets.data.flatMap((m) => m.stores);
  const states = [...new Set(stores.map((s) => s.state).filter((s): s is string => Boolean(s)))].sort();
  const cities = [...new Set(stores.filter((s) => !state || s.state === state).map((s) => s.city).filter((s): s is string => Boolean(s)))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  const visibleMarkets = markets.data.map((market) => ({ ...market, stores: market.stores.filter((s) =>
    (!state || s.state === state) && (!city || s.city === city) && (!onlySelected || selection[s.id]?.selected)
    && filterText(`${market.name} ${s.name} ${s.city ?? ""} ${s.state ?? ""} ${s.district ?? ""}`).includes(filterText(query)),
  ) })).filter((m) => m.stores.length);
  const clearFilters = () => { setQuery(""); setState(""); setCity(""); setOnlySelected(false); };

  async function persist(goSearch: boolean) {
    if (goSearch && active.data) { navigate(`/buscas/${active.data.id}`); return; }
    try {
      await save.mutateAsync(selectedIds.map(([store_id, v]) => ({ store_id, toll_round_trip: v.toll ? v.toll.replace(",", ".") : "0" })));
      setEdits({});
      if (goSearch) {
        try {
          const run = await start.mutateAsync({ list_id: lists.list!.id, store_ids: selectedIds.map(([id]) => id), allow_llm: true });
          navigate(`/buscas/${run.id}`);
        } catch (error) { toast.error(translate(errorMessage(error))); }
      }
    } catch { /* Saving displays its error and keeps edits available for correction. */ }
  }

  const busy = save.isPending || start.isPending;
  const ready = Boolean(lists.list?.item_count) && selectedIds.length > 0 && selectedIds.length <= 40 && !lists.isError;
  const searchButton = (size: "sm" | "lg" = "lg") => <Button size={size} className="max-w-full whitespace-normal" disabled={busy || active.isLoading || (!active.data && !ready)} loading={busy} onClick={() => void persist(true)}><Search aria-hidden className="size-4 shrink-0" /><span>{translate(active.data ? "Acompanhar busca em andamento" : "Verificar preços agora")}</span></Button>;

  return (
    <div className="pb-44 lg:pb-20">
      <PageHeader eyebrow={translate(priceCheckFlow ? "2 de 3 · Confirme os mercados; 3 · Inicie a busca" : undefined)} title={translate("Escolha onde comparar")} description={translate("Selecione as lojas em que você realmente compraria. Cada mercado coleta os preços de um jeito, sempre respeitando as regras de acesso do site.")} />
      <Card as="section" aria-label={translate("Iniciar verificação de preços")} className="mb-5 space-y-3 border-brand/30 bg-brand-soft/40 p-4 sm:p-5">
        <h2 className="text-lg font-bold">{translate("Sua próxima verificação")}</h2>
        <p>{translate(pluralize(lists.list?.item_count ?? 0, "produto", "produtos"))}{translate(" na lista · ")}{translate(pluralize(selectedIds.length, "loja escolhida", "lojas escolhidas"))}</p>
        <p className="text-sm text-ink-2">{translate("Escolha as lojas abaixo e clique para salvar a seleção e iniciar a busca. Você pode acompanhar o progresso na próxima tela.")}</p>
        <div className="flex flex-wrap items-center gap-3">{translate(searchButton())}<Link to="/buscar" className="text-sm font-semibold underline">{translate("Opções da busca e histórico")}</Link><Link to="/lista" className="text-sm font-semibold underline">{translate("Editar lista")}</Link></div>
        {!lists.list?.item_count && !lists.isLoading ? <p className="text-sm text-ink-2">{translate("Adicione pelo menos um produto à lista para começar.")}</p> : !selectedIds.length ? <p className="text-sm text-ink-2">{translate("Selecione pelo menos uma loja abaixo.")}</p> : null}
        {lists.isError ? <InlineAlert tone="danger" title={translate("Não foi possível carregar sua lista")} action={<Button variant="secondary" size="sm" onClick={() => void lists.refetch()}>{translate("Tentar novamente")}</Button>} /> : null}
      </Card>
      <Card className="mb-5 space-y-3 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label={translate("Buscar mercado ou filial")} htmlFor="market-filter"><Input id="market-filter" type="search" placeholder={translate("Nome, bairro ou cidade")} value={query} onChange={(e) => setQuery(e.target.value)} /></Field>
          <Field label={translate("UF")} htmlFor="market-state"><Select id="market-state" value={state} onChange={(e) => { setState(e.target.value); setCity(""); }}><option value="">{translate("Todos os estados")}</option>{states.map((uf) => <option key={uf}>{uf}</option>)}</Select></Field>
          <Field label={translate("Cidade")} htmlFor="market-city"><Select id="market-city" value={city} onChange={(e) => setCity(e.target.value)}><option value="">{translate("Todas as cidades")}</option>{cities.map((c) => <option key={c}>{c}</option>)}</Select></Field>
        </div>
        <SwitchRow id="only-selected" label={translate("Mostrar só minhas lojas")} checked={onlySelected} onCheckedChange={setOnlySelected} />
        <p className="text-sm text-ink-3">{translate("Filtros só mudam a exibição. Suas lojas selecionadas em outras cidades continuam na comparação.")}</p>
      </Card>
      {!hasHome ? (
        <div className="mb-5">
          <InlineAlert tone="info" title={translate("Cadastre seu endereço para ordenar por distância")} action={<Link to="/perfil#endereco" className={buttonClass({ variant: "secondary", size: "sm" })}><MapPin aria-hidden className="size-4" />{translate(" Adicionar endereço")}</Link>}>{translate("Com endereço e veículo, a comparação inclui o custo de ida e volta.")}</InlineAlert>
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {visibleMarkets.map((market) => (
          <MarketCard key={market.id} market={market} selection={selection} setSelection={setSelection} />
        ))}
      </div>
      {!visibleMarkets.length ? <EmptyState icon={StoreIcon} title={translate(stores.length ? "Nenhuma loja neste filtro" : "Nenhuma loja disponível")} action={stores.length ? <Button variant="secondary" onClick={clearFilters}>{translate("Limpar filtros")}</Button> : undefined}>{translate("Confira os filtros ou peça ao administrador para cadastrar uma filial das redes integradas.")}</EmptyState> : null}
      <div className="mt-5"><InlineAlert tone="info" title={translate("Não encontrou sua loja?")} action={<Link to={me.data?.user.role === "admin" ? "/admin" : "/ajuda"} className={buttonClass({ variant: "secondary", size: "sm" })}>{translate(me.data?.user.role === "admin" ? "Gerenciar mercados" : "Como começar")}</Link>}>{translate("O administrador pode cadastrar filiais e testar uma rede nova em Administração → Mercados → Adicionar novo mercado. O app usa reais (BRL) e endereços brasileiros.")}</InlineAlert></div>
      {selectedIds.length > 40 ? <InlineAlert tone="warn" title={translate("Selecione até 40 lojas")}>{translate("Reduza a seleção para salvar e buscar preços.")}</InlineAlert> : null}
      <div className="fixed inset-x-4 bottom-24 z-30 lg:static lg:mt-6">
        <Card className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 shadow-lift">
          <p className="text-sm">
            <span className="font-bold">{translate(pluralize(selectedIds.length, "loja selecionada", "lojas selecionadas"))}</span>
            {dirty ? <span className="text-ink-3">{translate(" · alterações não salvas")}</span> : null}
          </p>
          <div className="flex max-w-full flex-wrap gap-2">
            {dirty ? (
              <Button variant="secondary" size="sm" disabled={busy || selectedIds.length > 40} loading={save.isPending} onClick={() => void persist(false)}>{translate("Salvar")}</Button>
            ) : null}
            {translate(searchButton("sm"))}
          </div>
        </Card>
      </div>
      <p className="mt-6 flex items-center gap-2 text-xs text-ink-3">
        <MarketDot color="var(--color-brand)" />{translate(" As cores dos mercados são só identificação; o nome está sempre escrito.")}</p>
    </div>
  );
}
