import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { keys, useMarkets } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { Badge, Button, Card, Dialog, EmptyState, Field, Input, LoadingBlock, Select, Switch } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { WEEKDAYS } from "@/lib/labels";

export function SchedulesPage() {
  const client = useQueryClient();
  const schedules = useQuery({ queryKey: keys.schedules, queryFn: () => unwrap(api.GET("/api/v1/schedules")) });
  const markets = useMarkets();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Schemas["ScheduleIn"]>({ name: "Compra da semana", frequency: "weekly", weekday: 5, time_local: "07:00", store_ids: [], enabled: true });
  const invalidate = () => void client.invalidateQueries({ queryKey: keys.schedules });
  const create = useMutation({ mutationFn: (body: Schemas["ScheduleIn"]) => unwrap(api.POST("/api/v1/schedules", { body })), onSuccess: () => { invalidate(); setOpen(false); toast.success("Agendamento criado"); }, onError: (e) => toast.error(errorMessage(e)) });
  const update = useMutation({ mutationFn: ({ id, body }: { id: string; body: Schemas["ScheduleIn"] }) => unwrap(api.PUT("/api/v1/schedules/{schedule_id}", { params: { path: { schedule_id: id } }, body })), onSuccess: invalidate, onError: (e) => toast.error(errorMessage(e)) });
  const remove = useMutation({ mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/schedules/{schedule_id}", { params: { path: { schedule_id: id } } })), onSuccess: invalidate, onError: (e) => toast.error(errorMessage(e)) });
  const storeName = Object.fromEntries((markets.data ?? []).flatMap((m) => m.stores.map((s) => [s.id, `${m.name} ${s.name}`])));
  const selectedStores = (markets.data ?? []).flatMap((m) => m.stores.filter((s) => s.selected).map((s) => ({ id: s.id, label: `${m.name} ${s.name}` })));

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader
        title="Agendamentos"
        description="Busque os preços automaticamente, por exemplo toda sexta de manhã, para a comparação estar pronta quando você for às compras."
        actions={
          <Button onClick={() => { setForm((f) => ({ ...f, store_ids: selectedStores.map((s) => s.id) })); setOpen(true); }}>
            <Plus aria-hidden className="size-4" /> Novo agendamento
          </Button>
        }
      />
      {schedules.isLoading ? <LoadingBlock rows={2} /> : null}
      {schedules.data && !schedules.data.length ? (
        <EmptyState icon={CalendarClock} title="Nenhum agendamento">Crie um agendamento semanal para manter os preços sempre frescos.</EmptyState>
      ) : null}
      <ul className="space-y-3">
        {(schedules.data ?? []).map((s) => (
          <li key={s.id}>
            <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="font-semibold">{s.name}</p>
                <p className="text-sm text-ink-3">
                  {s.frequency === "weekly" ? `Toda ${WEEKDAYS[s.weekday ?? 0]?.toLowerCase()}` : "Todos os dias"} às {s.time_local} · {s.store_ids.length ? s.store_ids.map((id) => storeName[id] ?? "loja").join(", ") : "lojas selecionadas no momento"}
                </p>
                <p className="text-xs text-ink-3">{s.enabled ? `Próxima: ${formatDateTime(s.next_run_at)}` : "Pausado"}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={s.enabled ? "brand" : "neutral"}>{s.enabled ? "Ativo" : "Pausado"}</Badge>
                <Switch aria-label={`Ativar ${s.name}`} checked={s.enabled} onCheckedChange={(v) => update.mutate({ id: s.id, body: { name: s.name, list_id: s.list_id, frequency: s.frequency as "weekly" | "daily", weekday: s.weekday, time_local: s.time_local, store_ids: s.store_ids, enabled: v } })} />
                <Button variant="ghost" size="icon-sm" aria-label={`Excluir ${s.name}`} onClick={() => remove.mutate(s.id)}>
                  <Trash2 aria-hidden className="size-4" />
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Novo agendamento"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={() => create.mutate(form)} loading={create.isPending}>Criar</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Nome" htmlFor="schedule_name">
            <Input id="schedule_name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Frequência" htmlFor="frequency">
              <Select id="frequency" value={form.frequency} onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value as "weekly" | "daily", weekday: e.target.value === "weekly" ? (f.weekday ?? 5) : null }))}>
                <option value="weekly">Semanal</option>
                <option value="daily">Diária</option>
              </Select>
            </Field>
            <Field label="Horário" htmlFor="time_local">
              <Input id="time_local" type="time" value={form.time_local} onChange={(e) => setForm((f) => ({ ...f, time_local: e.target.value }))} />
            </Field>
          </div>
          {form.frequency === "weekly" ? (
            <Field label="Dia da semana" htmlFor="weekday">
              <Select id="weekday" value={form.weekday ?? 5} onChange={(e) => setForm((f) => ({ ...f, weekday: Number(e.target.value) }))}>
                {WEEKDAYS.map((d, i) => (
                  <option key={d} value={i}>{d}</option>
                ))}
              </Select>
            </Field>
          ) : null}
          <fieldset>
            <legend className="text-sm font-semibold">Lojas</legend>
            <p className="mb-2 text-sm text-ink-3">Vazio = usar as lojas selecionadas no momento da busca.</p>
            <div className="space-y-1">
              {selectedStores.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={form.store_ids?.includes(s.id)} onChange={(e) => setForm((f) => ({ ...f, store_ids: e.target.checked ? [...(f.store_ids ?? []), s.id] : (f.store_ids ?? []).filter((id) => id !== s.id) }))} />
                  {s.label}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      </Dialog>
    </div>
  );
}
