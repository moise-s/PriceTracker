import { translate, useLocale } from "@/lib/i18n";
import { ArrowRight, CheckCircle2, ListChecks, Scale, Search, Store } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useActiveRun, useComparison, useDefaultList, useMarkets, useMe, useRuns, useSaveStores } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { ProductImage } from "@/components/domain";
import { marketColor } from "@/lib/markets";
import { RecommendationCard } from "@/components/recommendation";
import { Badge, Button, Card, Checkbox, ErrorState, LoadingBlock, Progress } from "@/components/ui";
import { buttonClass, cn } from "@/components/ui/utils";
import { ago, pluralize } from "@/lib/format";
import { RUN_STATUS } from "@/lib/labels";

function greeting(): string {
  const hour = Number(new Intl.DateTimeFormat("pt-BR", { hour: "numeric", hourCycle: "h23", timeZone: "America/Sao_Paulo" }).format(new Date()));
  if (hour < 12) return translate("Bom dia");
  if (hour < 18) return translate("Boa tarde");
  return translate("Boa noite");
}

function Step({ index, done, title, detail, to, cta, icon: Icon }: { index: number; done: boolean; title: string; detail: string; to: string; cta: string; icon: typeof ListChecks }) {
  useLocale();
  return (
    <li className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3">
      <span className={cn("grid size-10 shrink-0 place-content-center rounded-full", done ? "bg-brand text-on-brand" : "bg-surface-3 text-ink-2")}>
        {done ? <CheckCircle2 aria-hidden className="size-5" /> : <Icon aria-hidden className="size-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          <span className="sr-only">{translate("Passo ")}{translate(index)}{translate(": ")}</span>
          {translate(title)}
        </p>
        <p className="truncate text-sm text-ink-3">{translate(detail)}</p>
      </div>
      <Link to={to} className={buttonClass({ variant: done ? "ghost" : "subtle", size: "sm" })}>
        {translate(cta)}
      </Link>
    </li>
  );
}

export function HomePage() {
  useLocale();
  const me = useMe();
  const { list, isLoading: listLoading } = useDefaultList();
  const markets = useMarkets();
  const saveStores = useSaveStores();
  const navigate = useNavigate();
  const [storeEdits, setStoreEdits] = useState<Record<string, boolean>>({});
  const isSelected = (store: { id: string; selected?: boolean | null }) => storeEdits[store.id] ?? store.selected ?? false;
  const chosenStores = (markets.data ?? []).flatMap((m) => m.stores.filter(isSelected));
  async function preparePriceCheck() {
    try {
      await saveStores.mutateAsync(chosenStores.map((store) => ({ store_id: store.id, toll_round_trip: store.toll_round_trip ?? "0" })));
      setStoreEdits({});
      navigate("/lista?flow=price-check");
    } catch { /* The mutation displays its error; the selection stays editable. */ }
  }
  const comparison = useComparison();
  const activeRun = useActiveRun();
  const runs = useRuns();

  const colors = Object.fromEntries((markets.data ?? []).map((m) => [m.slug, marketColor(m.slug, m.brand_color)]));
  const selectedStores = (markets.data ?? []).flatMap((m) => m.stores.filter(isSelected).map((s) => ({ ...s, market: m })));
  const itemCount = list?.item_count ?? 0;
  const lastRun = runs.data?.[0];
  const hasRecommendation = comparison.data && comparison.data.recommendation.kind !== "none";

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={translate(`${greeting()}, ${me.data?.user.display_name?.split(" ")[0] ?? ""}`)} title={translate("Onde a compra compensa esta semana")} description={translate("Compare sua cesta entre os mercados escolhidos, com cobertura, frescor dos preços e custo de ida e volta.")} />

      {activeRun.data ? (
        <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
          <Search aria-hidden className="size-6 shrink-0 animate-pulse text-brand" />
          <div className="flex-1">
            <p className="font-semibold">{translate("Busca em andamento")}</p>
            <Progress value={activeRun.data.done_targets} max={activeRun.data.total_targets} label={translate("Progresso da busca")} className="mt-2" />
          </div>
          <Link to={`/buscas/${activeRun.data.id}`} className={buttonClass({ variant: "secondary", size: "sm" })}>{translate("Acompanhar")}</Link>
        </Card>
      ) : null}

      {comparison.isLoading ? <LoadingBlock label={translate("Calculando a recomendação")} rows={1} /> : null}
      {hasRecommendation && comparison.data ? (
        <div className="space-y-3">
          <RecommendationCard comparison={comparison.data} colors={colors} compact />
          <div className="flex flex-wrap gap-2">
            <Link to="/comparar" className={buttonClass({ variant: "primary" })}>{translate("Ver detalhes da comparação ")}<ArrowRight aria-hidden className="size-4" />
            </Link>

          </div>
        </div>
      ) : null}

      <Card as="section" aria-labelledby="home-markets" className="space-y-4 p-4 sm:p-5">
        <h2 id="home-markets" className="text-lg font-semibold">{translate("Mercados da próxima verificação")}</h2>
        <p className="text-sm text-ink-2">{translate("Escolha aqui as lojas, inclusive os mercados novos. Ao atualizar, você revisa a lista, confirma os mercados e só então inicia a busca.")}</p>
        {markets.isLoading ? <LoadingBlock label={translate("Carregando mercados")} /> : null}
        {markets.error ? <ErrorState error={translate("Não foi possível carregar os mercados.")} onRetry={() => void markets.refetch()} /> : null}
        <div className="grid min-w-0 items-start gap-2 sm:grid-cols-2">
          {(markets.data ?? []).map((market) => <details key={market.id} className="min-w-0 rounded-xl border border-line p-3">
            <summary className="cursor-pointer break-words font-semibold">{market.name} <span className="text-xs font-normal text-ink-3">{translate("(")}{translate(market.stores.filter(isSelected).length)}{translate("/")}{translate(market.stores.length)}{translate(")")}</span></summary>
            <fieldset className="mt-3 max-h-56 space-y-3 overflow-y-auto">
              <legend className="sr-only">{market.name}</legend>
              {market.stores.map((store) => <div key={store.id} className="flex items-start gap-2">
                <Checkbox id={`home-store-${store.id}`} checked={isSelected(store)} disabled={saveStores.isPending} onCheckedChange={(checked) => setStoreEdits((previous) => ({ ...previous, [store.id]: checked === true }))} />
                <label htmlFor={`home-store-${store.id}`} className="min-w-0 cursor-pointer break-words text-sm">{store.name}<span className="block text-xs text-ink-3">{[store.city, store.state].filter(Boolean).join("/")}</span></label>
              </div>)}
              {!market.stores.length ? <p className="text-sm text-ink-3">{translate("Nenhuma loja disponível")}</p> : null}
            </fieldset>
          </details>)}
        </div>
        <p className="text-sm text-ink-2">{translate(pluralize(chosenStores.length, "loja escolhida", "lojas escolhidas"))}</p>
        {chosenStores.length > 40 ? <p className="text-sm text-danger">{translate("Selecione até 40 lojas")}</p> : null}
        <Button disabled={!markets.data || markets.isError || chosenStores.length > 40} loading={saveStores.isPending} onClick={() => void preparePriceCheck()}><Search aria-hidden className="size-4" />{translate("Atualizar preços")}</Button>
        <p className="text-xs text-ink-3">{translate("1. Revisar lista → 2. Confirmar mercados → 3. Buscar preços")}</p>
      </Card>
      <section aria-labelledby="passos" className="space-y-3">
        <h2 id="passos" className="text-lg font-semibold">
          {translate(hasRecommendation ? "Sua semana" : "Comece em 4 passos")}
        </h2>
        <ol className="grid grid-cols-1 gap-2.5 lg:grid-cols-2">
          <Step index={1} done={itemCount > 0} icon={ListChecks} title={translate("Monte sua lista")} detail={listLoading ? "Carregando…" : itemCount ? pluralize(itemCount, "item na lista", "itens na lista") : "Escolha produtos do catálogo"} to="/lista" cta={itemCount ? "Editar" : "Começar"} />
          <Step index={2} done={selectedStores.length > 0} icon={Store} title={translate("Escolha onde comparar")} detail={selectedStores.length ? selectedStores.map((s) => `${s.market.name} ${s.name}`).join(", ") : "Nenhum mercado escolhido"} to="/mercados" cta={selectedStores.length ? "Alterar" : "Escolher"} />
          <Step index={3} done={Boolean(lastRun && ["success", "partial"].includes(lastRun.status))} icon={Search} title={translate("Busque os preços")} detail={lastRun ? `${RUN_STATUS[lastRun.status]?.label ?? lastRun.status} · ${ago(lastRun.finished_at ?? lastRun.created_at)}` : "Ainda não houve busca"} to="/lista?flow=price-check" cta="Buscar" />
          <Step index={4} done={Boolean(hasRecommendation)} icon={Scale} title={translate("Veja onde compensa")} detail={hasRecommendation ? comparison.data!.recommendation.headline : "Disponível depois da primeira busca"} to="/comparar" cta="Ver" />
        </ol>
      </section>

      {list && list.items.length ? (
        <section aria-labelledby="na-lista" className="space-y-3">
          <div className="flex items-end justify-between">
            <h2 id="na-lista" className="text-lg font-semibold">{translate("Na sua lista")}</h2>
            <Link to="/lista" className="text-sm font-semibold text-brand hover:underline">{translate("Editar lista")}</Link>
          </div>
          <ul tabIndex={0} aria-label={translate("Itens da sua lista (role para o lado para ver todos)")} className="scrollbar-none -mx-4 flex gap-3 overflow-x-auto rounded-lg px-4 pb-1 sm:mx-0 sm:px-0">
            {list.items.map((item) => (
              <li key={item.id} className="w-28 shrink-0">
                <ProductImage image={item.image} category={item.category} name={item.product_name} className="rounded-xl" />
                <p className="mt-1.5 line-clamp-2 text-sm leading-tight font-semibold">{item.product_name}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {lastRun ? (
        <p className="text-sm text-ink-3">{translate("Última busca: ")}<Badge tone={RUN_STATUS[lastRun.status]?.tone ?? "neutral"}>{translate(RUN_STATUS[lastRun.status]?.label ?? lastRun.status)}</Badge> {translate(ago(lastRun.finished_at ?? lastRun.created_at))}{translate(".")}{translate(" ")}
          <Link className="font-semibold text-brand hover:underline" to={`/buscas/${lastRun.id}`}>{translate("Ver detalhes")}</Link>
        </p>
      ) : null}
    </div>
  );
}
