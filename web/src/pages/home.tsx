import { ArrowRight, CheckCircle2, ListChecks, Scale, Search, Store } from "lucide-react";
import { Link } from "react-router";
import { useActiveRun, useComparison, useDefaultList, useMarkets, useMe, useRuns } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { ProductImage, marketColor } from "@/components/domain";
import { RecommendationCard } from "@/components/recommendation";
import { Badge, buttonClass, Card, cn, LoadingBlock, Progress } from "@/components/ui";
import { ago, pluralize } from "@/lib/format";
import { RUN_STATUS } from "@/lib/labels";

function greeting(): string {
  const hour = Number(new Intl.DateTimeFormat("pt-BR", { hour: "numeric", hourCycle: "h23", timeZone: "America/Sao_Paulo" }).format(new Date()));
  if (hour < 12) return "Bom dia";
  if (hour < 18) return "Boa tarde";
  return "Boa noite";
}

function Step({ index, done, title, detail, to, cta, icon: Icon }: { index: number; done: boolean; title: string; detail: string; to: string; cta: string; icon: typeof ListChecks }) {
  return (
    <li className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3">
      <span className={cn("grid size-10 shrink-0 place-content-center rounded-full", done ? "bg-brand text-white" : "bg-surface-3 text-ink-2")}>
        {done ? <CheckCircle2 aria-hidden className="size-5" /> : <Icon aria-hidden className="size-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          <span className="sr-only">Passo {index}: </span>
          {title}
        </p>
        <p className="truncate text-sm text-ink-3">{detail}</p>
      </div>
      <Link to={to} className={buttonClass({ variant: done ? "ghost" : "subtle", size: "sm" })}>
        {cta}
      </Link>
    </li>
  );
}

export function HomePage() {
  const me = useMe();
  const { list, isLoading: listLoading } = useDefaultList();
  const markets = useMarkets();
  const comparison = useComparison();
  const activeRun = useActiveRun();
  const runs = useRuns();

  const colors = Object.fromEntries((markets.data ?? []).map((m) => [m.slug, marketColor(m.slug, m.brand_color)]));
  const selectedStores = (markets.data ?? []).flatMap((m) => m.stores.filter((s) => s.selected).map((s) => ({ ...s, market: m })));
  const itemCount = list?.item_count ?? 0;
  const lastRun = runs.data?.[0];
  const hasRecommendation = comparison.data && comparison.data.recommendation.kind !== "none";

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={`${greeting()}, ${me.data?.user.display_name?.split(" ")[0] ?? ""}`} title="Onde a compra compensa esta semana" description="Compare sua cesta entre os mercados escolhidos, com cobertura, frescor dos preços e custo de ida e volta." />

      {activeRun.data ? (
        <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
          <Search aria-hidden className="size-6 shrink-0 animate-pulse text-brand" />
          <div className="flex-1">
            <p className="font-semibold">Busca em andamento</p>
            <Progress value={activeRun.data.done_targets} max={activeRun.data.total_targets} label="Progresso da busca" className="mt-2" />
          </div>
          <Link to={`/buscas/${activeRun.data.id}`} className={buttonClass({ variant: "secondary", size: "sm" })}>
            Acompanhar
          </Link>
        </Card>
      ) : null}

      {comparison.isLoading ? <LoadingBlock label="Calculando a recomendação" rows={1} /> : null}
      {hasRecommendation && comparison.data ? (
        <div className="space-y-3">
          <RecommendationCard comparison={comparison.data} colors={colors} compact />
          <div className="flex flex-wrap gap-2">
            <Link to="/comparar" className={buttonClass({ variant: "primary" })}>
              Ver detalhes da comparação <ArrowRight aria-hidden className="size-4" />
            </Link>
            <Link to="/buscar" className={buttonClass({ variant: "secondary" })}>
              <Search aria-hidden className="size-4" /> Atualizar preços
            </Link>
          </div>
        </div>
      ) : null}

      <section aria-labelledby="passos" className="space-y-3">
        <h2 id="passos" className="text-lg font-semibold">
          {hasRecommendation ? "Sua semana" : "Comece em 4 passos"}
        </h2>
        <ol className="grid gap-2.5 lg:grid-cols-2">
          <Step index={1} done={itemCount > 0} icon={ListChecks} title="Monte sua lista" detail={listLoading ? "Carregando…" : itemCount ? pluralize(itemCount, "item na lista", "itens na lista") : "Escolha produtos do catálogo"} to="/lista" cta={itemCount ? "Editar" : "Começar"} />
          <Step index={2} done={selectedStores.length > 0} icon={Store} title="Escolha onde comparar" detail={selectedStores.length ? selectedStores.map((s) => `${s.market.name} ${s.name}`).join(", ") : "Nenhum mercado escolhido"} to="/mercados" cta={selectedStores.length ? "Alterar" : "Escolher"} />
          <Step index={3} done={Boolean(lastRun && ["success", "partial"].includes(lastRun.status))} icon={Search} title="Busque os preços" detail={lastRun ? `${RUN_STATUS[lastRun.status]?.label ?? lastRun.status} · ${ago(lastRun.finished_at ?? lastRun.created_at)}` : "Ainda não houve busca"} to="/buscar" cta="Buscar" />
          <Step index={4} done={Boolean(hasRecommendation)} icon={Scale} title="Veja onde compensa" detail={hasRecommendation ? comparison.data!.recommendation.headline : "Disponível depois da primeira busca"} to="/comparar" cta="Ver" />
        </ol>
      </section>

      {list && list.items.length ? (
        <section aria-labelledby="na-lista" className="space-y-3">
          <div className="flex items-end justify-between">
            <h2 id="na-lista" className="text-lg font-semibold">Na sua lista</h2>
            <Link to="/lista" className="text-sm font-semibold text-brand hover:underline">Editar lista</Link>
          </div>
          <ul className="scrollbar-none -mx-4 flex gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
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
        <p className="text-sm text-ink-3">
          Última busca: <Badge tone={RUN_STATUS[lastRun.status]?.tone ?? "neutral"}>{RUN_STATUS[lastRun.status]?.label ?? lastRun.status}</Badge> {ago(lastRun.finished_at ?? lastRun.created_at)}.{" "}
          <Link className="font-semibold text-brand hover:underline" to={`/buscas/${lastRun.id}`}>Ver detalhes</Link>
        </p>
      ) : null}
    </div>
  );
}
