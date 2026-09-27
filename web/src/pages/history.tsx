import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, ExternalLink, LineChart as LineChartIcon, Table2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { useDefaultList, useHistory } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { Badge, Button, Card, EmptyState, ErrorState, LoadingBlock, Select } from "@/components/ui";
import { cn } from "@/components/ui/utils";
import { formatDate, formatShortDate, money, unitPrice } from "@/lib/format";

// Validated categorical palette (dataviz reference order), light/dark steps.
// A store's first-market colour is its market's token; extra stores of the same
// market take the next free slot. Colour follows the store, never its rank.
const SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
const MARKET_SLOT: Record<string, number> = { imperatriz: 0, fort: 1, angeloni: 2, bistek: 6 };

function useSeriesColors(series: Schemas["HistorySeriesOut"][]): Record<string, string> {
  const dark = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  const palette = dark ? SERIES_DARK : SERIES_LIGHT;
  const used = new Set<number>();
  const colors: Record<string, string> = {};
  for (const s of series) {
    const slot = MARKET_SLOT[s.market_slug];
    if (slot !== undefined && !used.has(slot)) {
      used.add(slot);
      colors[s.store_id] = `var(--color-market-${s.market_slug})`;
    }
  }
  for (const s of series) {
    if (colors[s.store_id]) continue;
    const slot = palette.findIndex((_, i) => !used.has(i));
    const index = slot === -1 ? 0 : slot;
    used.add(index);
    colors[s.store_id] = palette[index]!;
  }
  return colors;
}

const DAY_FMT = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" });

type Row = { t: number } & Record<string, number | null>;

function buildRows(series: Schemas["HistorySeriesOut"][]): Row[] {
  const byDay = new Map<string, Row>();
  for (const s of series) {
    for (const point of s.points) {
      if (point.flagged || point.unit_price === null || point.unit_price === undefined) continue;
      const day = DAY_FMT.format(new Date(point.observed_at));
      const t = new Date(`${day}T12:00:00-03:00`).getTime();
      const row = byDay.get(day) ?? ({ t } as Row);
      row[s.store_id] = Number(point.unit_price);
      byDay.set(day, row);
    }
  }
  return [...byDay.values()].sort((a, b) => a.t - b.t);
}

function ChartTooltip({ active, label, payload, names, unit }: { active?: boolean; label?: number; payload?: Array<{ dataKey?: string | number; value?: number; color?: string }>; names: Record<string, string>; unit: string }) {
  if (!active || !payload?.length || label === undefined) return null;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 shadow-lift">
      <p className="mb-1 text-xs text-ink-3">{formatDate(new Date(label).toISOString())}</p>
      <ul className="space-y-1">
        {payload
          .filter((p) => p.value !== null && p.value !== undefined)
          .map((p) => (
            <li key={String(p.dataKey)} className="flex items-center gap-2 text-sm">
              <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: p.color }} />
              <span className="font-bold tabular text-ink">{unitPrice(p.value ?? null, unit)}</span>
              <span className="text-ink-3">{names[String(p.dataKey)]}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}

export function HistoryPage() {
  const { list, isLoading: listLoading } = useDefaultList();
  const products = list?.items ?? [];
  const [productId, setProductId] = useState<string | undefined>();
  const [days, setDays] = useState(90);
  const [asTable, setAsTable] = useState(false);
  const [now] = useState(() => Date.now());
  const current = productId ?? products[0]?.product_id;
  const history = useHistory(current, days);
  const client = useQueryClient();

  const series = useMemo(() => [...(history.data?.series ?? [])].sort((a, b) => `${a.market_name}${a.store_name}`.localeCompare(`${b.market_name}${b.store_name}`)), [history.data]);
  const colors = useSeriesColors(series);
  const rows = useMemo(() => buildRows(series), [series]);
  const names = Object.fromEntries(series.map((s) => [s.store_id, `${s.market_name} · ${s.store_name}`]));
  const unit = series.flatMap((s) => s.points).find((p) => p.unit_price_unit)?.unit_price_unit ?? "un";
  const freshness = history.data?.freshness_days ?? 7;
  const staleCutoff = now - freshness * 86_400_000;
  const flagged = series.flatMap((s) => s.points.filter((p) => p.flagged).map((p) => ({ ...p, store: names[s.store_id] })));

  async function review(observationId: string, decision: "confirm" | "reject") {
    try {
      await unwrap(api.POST("/api/v1/observations/{observation_id}/review", { params: { path: { observation_id: observationId }, query: { decision } } }));
      toast.success(decision === "confirm" ? "Preço confirmado" : "Preço descartado");
      void client.invalidateQueries({ queryKey: ["history"] });
      void client.invalidateQueries({ queryKey: ["comparison"] });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  if (listLoading) return <LoadingBlock label="Carregando" />;
  if (!products.length) {
    return (
      <>
        <PageHeader title="Histórico de preços" />
        <EmptyState icon={LineChartIcon} title="Sem produtos na lista">Adicione produtos e faça buscas para acompanhar a evolução dos preços.</EmptyState>
      </>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Histórico de preços" description={`Preço comparável (por kg, litro ou unidade) em cada loja. Preços com mais de ${freshness} dias ficam no histórico, mas não entram na recomendação da semana.`} />
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-56 flex-1 space-y-1.5 sm:flex-none">
          <span className="text-sm font-semibold">Produto</span>
          <Select aria-label="Produto" value={current} onChange={(e) => setProductId(e.target.value)}>
            {products.map((item) => (
              <option key={item.product_id} value={item.product_id}>
                {item.product_name}
              </option>
            ))}
          </Select>
        </label>
        <div className="flex gap-1 rounded-full bg-surface-3 p-1" role="group" aria-label="Período">
          {[30, 90, 180, 365].map((value) => (
            <button key={value} type="button" aria-pressed={days === value} onClick={() => setDays(value)} className={cn("h-9 rounded-full px-3.5 text-sm font-semibold", days === value ? "bg-surface text-ink shadow-card" : "text-ink-2")}>
              {value === 365 ? "1 ano" : `${value} dias`}
            </button>
          ))}
        </div>
        <Button variant="secondary" size="sm" className="ml-auto" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>
          {asTable ? <LineChartIcon aria-hidden className="size-4" /> : <Table2 aria-hidden className="size-4" />}
          {asTable ? "Ver gráfico" : "Ver tabela"}
        </Button>
      </div>

      {history.isLoading ? <LoadingBlock label="Carregando histórico" rows={2} /> : null}
      {history.error ? <ErrorState error={errorMessage(history.error)} onRetry={() => void history.refetch()} /> : null}

      {history.data && !series.length ? (
        <EmptyState icon={LineChartIcon} title="Ainda sem histórico">Nenhuma busca encontrou este produto no período.</EmptyState>
      ) : null}

      {series.length ? (
        <>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {series.map((s) => {
              const last = s.points.filter((p) => !p.flagged).at(-1);
              return (
                <li key={s.store_id}>
                  <Card className="p-4">
                    <p className="flex items-center gap-2 text-sm font-semibold">
                      <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: colors[s.store_id] }} />
                      {names[s.store_id]}
                    </p>
                    <p className="mt-2 font-display text-2xl font-bold">{unitPrice(s.stats.last, unit)}</p>
                    <p className="text-xs text-ink-3">
                      mín. {unitPrice(s.stats.min, unit)} · mediana {unitPrice(s.stats.median, unit)} · {s.stats.count} obs.
                    </p>
                    {last?.stale ? <Badge tone="warn" className="mt-2">Último preço desatualizado ({formatDate(last.observed_at)})</Badge> : null}
                  </Card>
                </li>
              );
            })}
          </ul>

          {!asTable ? (
            <Card className={cn("p-4 transition-opacity", history.isFetching && "opacity-60")}>
              <h2 className="mb-1 text-base font-semibold">{history.data?.product_name} — preço por {unit}</h2>
              <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2" aria-label="Legenda">
                {series.map((s) => (
                  <li key={s.store_id} className="inline-flex items-center gap-2">
                    <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: colors[s.store_id] }} />
                    {names[s.store_id]}
                  </li>
                ))}
                <li className="inline-flex items-center gap-2 text-ink-3">
                  <span aria-hidden className="h-3 w-4 rounded-sm bg-surface-3" /> preços com mais de {freshness} dias
                </li>
              </ul>
              <div className="h-72 w-full" role="img" aria-label={`Gráfico da evolução do preço por ${unit}. Use “Ver tabela” para os valores.`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                    <CartesianGrid vertical={false} stroke="var(--color-line)" strokeWidth={1} />
                    {rows.length && rows[0]!.t < staleCutoff ? <ReferenceArea x1={rows[0]!.t} x2={Math.min(staleCutoff, rows.at(-1)!.t)} fill="var(--color-surface-3)" fillOpacity={0.6} ifOverflow="hidden" /> : null}
                    <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={(t: number) => formatShortDate(t)} tick={{ fill: "var(--color-ink-3)", fontSize: 12 }} axisLine={{ stroke: "var(--color-line-strong)" }} tickLine={false} minTickGap={24} />
                    <YAxis width={64} tickFormatter={(v: number) => money(v)} tick={{ fill: "var(--color-ink-3)", fontSize: 12 }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
                    <Tooltip content={<ChartTooltip names={names} unit={unit} />} cursor={{ stroke: "var(--color-ink-3)", strokeWidth: 1 }} />
                    {series.map((s) => (
                      <Line
                        key={s.store_id}
                        type="monotone"
                        dataKey={s.store_id}
                        name={names[s.store_id]}
                        stroke={colors[s.store_id]}
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        connectNulls
                        dot={{ r: 4, strokeWidth: 2, stroke: "var(--color-surface)", fill: colors[s.store_id] }}
                        activeDot={{ r: 6, strokeWidth: 2, stroke: "var(--color-surface)" }}
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          ) : (
            <Card className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <caption className="sr-only">Observações de preço de {history.data?.product_name}</caption>
                <thead className="bg-surface-2">
                  <tr>
                    <th scope="col" className="px-4 py-2.5">Data</th>
                    <th scope="col" className="px-4 py-2.5">Loja</th>
                    <th scope="col" className="px-4 py-2.5">Anúncio</th>
                    <th scope="col" className="px-4 py-2.5 text-right">Preço</th>
                    <th scope="col" className="px-4 py-2.5 text-right">Por {unit}</th>
                    <th scope="col" className="px-4 py-2.5">Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {series
                    .flatMap((s) => s.points.map((p) => ({ ...p, store: names[s.store_id] })))
                    .sort((a, b) => b.observed_at.localeCompare(a.observed_at))
                    .map((p) => (
                      <tr key={p.observation_id} className="border-t border-line">
                        <td className="px-4 py-2 tabular">{formatDate(p.observed_at)}</td>
                        <td className="px-4 py-2">{p.store}</td>
                        <td className="max-w-64 truncate px-4 py-2">
                          {p.url ? (
                            <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                              {p.title} <ExternalLink aria-hidden className="size-3" />
                            </a>
                          ) : (
                            p.title
                          )}
                        </td>
                        <td className="px-4 py-2 text-right tabular">{money(p.price)}</td>
                        <td className="px-4 py-2 text-right tabular">{unitPrice(p.unit_price, p.unit_price_unit)}</td>
                        <td className="px-4 py-2">{p.flagged ? <Badge tone="danger">Em revisão</Badge> : p.stale ? <Badge tone="warn">Desatualizado</Badge> : <Badge tone="brand">Atual</Badge>}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </Card>
          )}

          {flagged.length ? (
            <Card className="space-y-3 p-4">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <AlertTriangle aria-hidden className="size-5 text-warn" /> Preços sinalizados para revisão
              </h2>
              <p className="text-sm text-ink-3">Mudanças implausíveis não são descartadas em silêncio: ficam fora da recomendação até você confirmar.</p>
              <ul className="space-y-2">
                {flagged.map((p) => (
                  <li key={p.observation_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
                    <span>
                      <span className="font-semibold">{money(p.price)}</span> · {p.store} · {formatDate(p.observed_at)}
                      {p.outlier_reason ? <span className="block text-xs text-ink-3">{p.outlier_reason}</span> : null}
                    </span>
                    <span className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => void review(p.observation_id, "confirm")}>
                        <Check aria-hidden className="size-4" /> Confirmar
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => void review(p.observation_id, "reject")}>
                        <X aria-hidden className="size-4" /> Descartar
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
