import { ArrowRight, Ban, Bot, ListChecks, RotateCcw, Scale, Search, Store } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { errorMessage, type Schemas } from "@/api/client";
import { useActiveRun, useCancelRun, useDefaultList, useMarkets, useRetryRun, useRun, useRuns, useStartRun } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { MarketDot, StatusPill, marketColor } from "@/components/domain";
import { Badge, Button, buttonClass, Card, EmptyState, ErrorState, InlineAlert, LoadingBlock, Progress, SwitchRow } from "@/components/ui";
import { ago, formatDateTime, money, pluralize, unitPrice } from "@/lib/format";
import { RUN_STATUS, TARGET_STATUS } from "@/lib/labels";

export function SearchPage() {
  const { list } = useDefaultList();
  const markets = useMarkets();
  const active = useActiveRun();
  const runs = useRuns();
  const start = useStartRun();
  const navigate = useNavigate();
  const [allowLlm, setAllowLlm] = useState(true);

  if (active.data) return <Navigate to={`/buscas/${active.data.id}`} replace />;
  if (markets.isLoading || !list) return <LoadingBlock label="Preparando a busca" />;

  const selected = (markets.data ?? []).flatMap((m) => m.stores.filter((s) => s.selected).map((s) => ({ store: s, market: m })));
  const items = list.item_count;
  const total = items * selected.length;
  const heavy = selected.filter((s) => s.market.slug === "bistek" || s.market.slug === "fort").length;
  const estimateMinutes = Math.max(1, Math.round((items * (selected.length - heavy) * 2 + items * heavy * 8) / 60));

  async function onStart() {
    try {
      const run = await start.mutateAsync({ allow_llm: allowLlm });
      navigate(`/buscas/${run.id}`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Buscar preços" description="A busca roda em segundo plano: você pode sair desta tela e voltar depois." />
      {!items || !selected.length ? (
        <EmptyState
          icon={!items ? ListChecks : Store}
          title={!items ? "Sua lista está vazia" : "Nenhuma loja escolhida"}
          action={<Link className={buttonClass()} to={!items ? "/lista" : "/mercados"}>{!items ? "Montar lista" : "Escolher mercados"}</Link>}
        >
          {!items ? "Adicione produtos para comparar." : "Escolha pelo menos uma loja para buscar os preços."}
        </EmptyState>
      ) : (
        <Card className="space-y-5 p-5 sm:p-6">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-ink-3">Produtos</p>
              <p className="font-display text-3xl font-bold tabular">{items}</p>
            </div>
            <div>
              <p className="text-sm text-ink-3">Lojas</p>
              <p className="font-display text-3xl font-bold tabular">{selected.length}</p>
            </div>
            <div>
              <p className="text-sm text-ink-3">Consultas</p>
              <p className="font-display text-3xl font-bold tabular">{total}</p>
            </div>
          </div>
          <ul className="flex flex-wrap gap-2">
            {selected.map(({ store, market }) => (
              <li key={store.id} className="inline-flex items-center gap-2 rounded-full bg-surface-2 px-3 py-1.5 text-sm ring-1 ring-line">
                <MarketDot color={marketColor(market.slug, market.brand_color)} />
                <span className="font-semibold">{market.name}</span> {store.name}
              </li>
            ))}
          </ul>
          <SwitchRow id="allow_llm" label={<span className="inline-flex items-center gap-2"><Bot aria-hidden className="size-4" /> Usar IA só quando a leitura normal falhar</span>} description="A IA nunca inventa produtos ou preços: tudo o que ela devolve é conferido contra o conteúdo da página." checked={allowLlm} onCheckedChange={setAllowLlm} />
          <InlineAlert tone="neutral">
            Tempo estimado: cerca de {estimateMinutes} min. Os sites são consultados devagar, respeitando as regras de acesso de cada um.
          </InlineAlert>
          <Button size="lg" className="w-full" onClick={() => void onStart()} loading={start.isPending}>
            <Search aria-hidden className="size-5" /> Buscar preços agora
          </Button>
        </Card>
      )}
      {runs.data?.length ? (
        <section aria-labelledby="buscas-recentes" className="space-y-2">
          <h2 id="buscas-recentes" className="text-lg font-semibold">Buscas recentes</h2>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {runs.data.map((run) => {
              const meta = RUN_STATUS[run.status] ?? { label: run.status, tone: "neutral" as const };
              return (
                <li key={run.id}>
                  <Link to={`/buscas/${run.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2">
                    <span>
                      <span className="block font-semibold">{formatDateTime(run.created_at)}</span>
                      <span className="text-sm text-ink-3">
                        {pluralize(run.total_targets, "consulta", "consultas")} · {run.trigger === "schedule" ? "agendada" : run.trigger === "retry" ? "repetição" : run.trigger === "cli" ? "linha de comando" : "manual"}
                      </span>
                    </span>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function groupTargets(targets: Schemas["RunTargetOut"][]) {
  const groups = new Map<string, { key: string; market: string; marketSlug: string; store: string; targets: Schemas["RunTargetOut"][] }>();
  for (const target of targets) {
    const key = target.store_id;
    if (!groups.has(key)) groups.set(key, { key, market: target.market_name, marketSlug: target.market_slug, store: target.store_name, targets: [] });
    groups.get(key)!.targets.push(target);
  }
  return [...groups.values()];
}

export function RunPage() {
  const { id } = useParams();
  const run = useRun(id);
  const markets = useMarkets();
  const cancel = useCancelRun();
  const retry = useRetryRun();
  const navigate = useNavigate();
  const colors = useMemo(() => Object.fromEntries((markets.data ?? []).map((m) => [m.slug, marketColor(m.slug, m.brand_color)])), [markets.data]);

  if (run.isLoading) return <LoadingBlock label="Carregando busca" />;
  if (run.error || !run.data) return <ErrorState error="Busca não encontrada." />;
  const data = run.data;
  const meta = RUN_STATUS[data.status] ?? { label: data.status, tone: "neutral" as const, icon: Search };
  const running = ["queued", "running"].includes(data.status);
  const groups = groupTargets(data.targets);
  const failures = data.targets.filter((t) => ["blocked", "timeout", "adapter_error", "needs_llm"].includes(t.status)).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={running ? "Buscando preços…" : "Resultado da busca"}
        description={`Iniciada ${ago(data.created_at)}${data.finished_at ? ` · terminou ${ago(data.finished_at)}` : ""}`}
        actions={
          running ? (
            <Button variant="secondary" onClick={() => cancel.mutate(data.id)} loading={cancel.isPending} disabled={data.cancel_requested}>
              <Ban aria-hidden className="size-4" /> {data.cancel_requested ? "Cancelando…" : "Cancelar"}
            </Button>
          ) : (
            <>
              {data.retryable ? (
                <Button variant="secondary" loading={retry.isPending} onClick={() => retry.mutate(data.id, { onSuccess: (r) => navigate(`/buscas/${r.id}`) })}>
                  <RotateCcw aria-hidden className="size-4" /> Repetir falhas ({data.retryable})
                </Button>
              ) : null}
              <Link to="/comparar" className={buttonClass()}>
                <Scale aria-hidden className="size-4" /> Ver onde compensa
              </Link>
            </>
          )
        }
      />
      <Card className="space-y-4 p-5" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge tone={meta.tone} icon={meta.icon} spin={data.status === "running"}>
            {meta.label}
          </Badge>
          <span className="text-sm font-semibold tabular text-ink-2">
            {data.done_targets} de {data.total_targets} consultas
          </span>
        </div>
        <Progress value={data.done_targets} max={data.total_targets} label="Progresso da busca" tone={data.status === "partial" ? "warn" : "brand"} />
        <ul className="flex flex-wrap gap-2 text-sm">
          {Object.entries(data.counts)
            .sort()
            .map(([status, count]) => (
              <li key={status}>
                <StatusPill status={status} /> <span className="tabular font-semibold">{count}</span>
              </li>
            ))}
        </ul>
        {data.status === "partial" ? (
          <InlineAlert tone="warn" title="Algumas consultas falharam">
            {pluralize(failures, "consulta falhou", "consultas falharam")}. Os resultados obtidos foram mantidos; repita só as falhas quando quiser.
          </InlineAlert>
        ) : null}
        {data.status === "failed" ? <InlineAlert tone="danger" title="Nenhum mercado respondeu corretamente">Veja os detalhes abaixo e tente novamente mais tarde.</InlineAlert> : null}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map((group) => {
          const done = group.targets.filter((t) => !["pending", "running"].includes(t.status)).length;
          return (
            <Card key={group.key} className="overflow-hidden">
              <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
                <span className="inline-flex min-w-0 items-center gap-2">
                  <MarketDot color={colors[group.marketSlug]} />
                  <span className="truncate">
                    <span className="font-bold">{group.market}</span> <span className="text-ink-3">{group.store}</span>
                  </span>
                </span>
                <span className="text-sm tabular text-ink-3">
                  {done}/{group.targets.length}
                </span>
              </div>
              <ul className="divide-y divide-line">
                {group.targets.map((target) => (
                  <li key={target.id} className="flex items-start justify-between gap-3 px-4 py-2.5">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold">{target.product_name}</p>
                      {target.observation ? (
                        <p className="truncate text-xs text-ink-3">
                          {String(target.observation.title ?? "")} · {money(target.observation.price as string)}
                          {target.observation.unit_price ? ` (${unitPrice(target.observation.unit_price as string, target.observation.unit_price_unit as string)})` : ""}
                        </p>
                      ) : target.error_detail ? (
                        <p className="line-clamp-2 text-xs text-ink-3">{target.error_detail}</p>
                      ) : null}
                    </div>
                    <StatusPill status={target.status} />
                  </li>
                ))}
              </ul>
            </Card>
          );
        })}
      </div>

      <details className="rounded-xl border border-line bg-surface px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold">O que significa cada estado</summary>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {Object.entries(TARGET_STATUS).map(([key, value]) => (
            <div key={key} className="flex gap-2">
              <dt>
                <StatusPill status={key} />
              </dt>
              <dd className="text-ink-3">{value.help}</dd>
            </div>
          ))}
        </dl>
      </details>
      {data.events.length ? (
        <details className="rounded-xl border border-line bg-surface px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold">Registro da busca</summary>
          <ol className="mt-3 space-y-1 text-xs text-ink-3">
            {data.events.map((event) => (
              <li key={event.id}>
                <span className="tabular">{formatDateTime(event.created_at)}</span> — {event.message}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
      {!running ? (
        <Link to="/comparar" className={buttonClass({ size: "lg", className: "w-full sm:w-auto" })}>
          Ver onde compensa <ArrowRight aria-hidden className="size-5" />
        </Link>
      ) : null}
    </div>
  );
}
