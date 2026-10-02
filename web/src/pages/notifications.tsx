import { translate, useLocale } from "@/lib/i18n";
import { BellRing, CheckCheck, Scale } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { useAlerts, useDefaultList, useMarkNotificationsRead, useNotifications, useSetAlert } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { Badge, Button, Card, EmptyState, Field, Input, LoadingBlock, Section, Select } from "@/components/ui";
import { buttonClass, cn } from "@/components/ui/utils";
import { ago, money, parseMoneyInput } from "@/lib/format";

function NewAlertForm() {
  useLocale();
  const { list } = useDefaultList();
  const alerts = useAlerts();
  const setAlert = useSetAlert();
  const taken = new Set((alerts.data ?? []).map((a) => a.product_id));
  const options = (list?.items ?? []).filter((item) => !taken.has(item.product_id));
  const [productId, setProductId] = useState("");
  const [target, setTarget] = useState("");
  const chosen = productId || options[0]?.product_id || "";
  const amount = parseMoneyInput(target);
  if (!options.length) return null;
  return (
    <Card className="flex flex-wrap items-end gap-3 p-4">
      <Field label={translate("Produto da sua lista")} htmlFor="alert_product" className="min-w-0 flex-1 basis-56">
        <Select id="alert_product" value={chosen} onChange={(e) => setProductId(e.target.value)}>
          {options.map((item) => (
            <option key={item.product_id} value={item.product_id}>
              {item.product_name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={translate("Avisar a partir de (R$)")} htmlFor="alert_target" className="w-40">
        <Input id="alert_target" inputMode="decimal" placeholder={translate("0,00")} value={target} onChange={(e) => setTarget(e.target.value)} />
      </Field>
      <Button
        disabled={!chosen || amount === null}
        loading={setAlert.isPending}
        onClick={() => setAlert.mutate({ productId: chosen, body: { target_price: String(amount), enabled: true } }, { onSuccess: () => { setTarget(""); setProductId(""); } })}
      >
        <BellRing aria-hidden className="size-4" />{translate(" Criar alerta")}</Button>
    </Card>
  );
}

export function NotificationsPage() {
  useLocale();
  const notifications = useNotifications();
  const alerts = useAlerts();
  const markRead = useMarkNotificationsRead();
  if (notifications.isLoading || alerts.isLoading) return <LoadingBlock label={translate("Carregando avisos")} rows={3} />;
  const items = notifications.data?.items ?? [];
  const unread = notifications.data?.unread ?? 0;
  return (
    <div className="space-y-8">
      <PageHeader
        title={translate("Avisos")}
        description={translate("Alertas de preço disparados pelas suas buscas. Nada sai daqui: não há e-mail nem notificação externa.")}
        actions={
          unread ? (
            <Button variant="secondary" onClick={() => markRead.mutate(undefined)} loading={markRead.isPending}>
              <CheckCheck aria-hidden className="size-4" />{translate(" Marcar todos como lidos")}</Button>
          ) : null
        }
      />

      <Section title={translate("Recentes")} description={translate(unread ? `${unread} não lido${unread > 1 ? "s" : ""}` : undefined)}>
        {items.length ? (
          <ul className="space-y-3">
            {items.map((note) => {
              const productId = typeof note.data.product_id === "string" ? note.data.product_id : null;
              return (
                <li key={note.id}>
                  <Card className={cn("space-y-2 p-4", !note.read_at && "ring-2 ring-brand/30")}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="flex items-center gap-2 font-semibold">
                        {!note.read_at ? (
                          <>
                            <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-accent" />
                            <span className="sr-only">{translate("Não lido: ")}</span>
                          </>
                        ) : null}
                        {note.title}
                      </p>
                      <span className="text-xs text-ink-3">{translate(ago(note.created_at))}</span>
                    </div>
                    <p className="text-sm text-ink-2">{translate(note.body)}</p>
                    <div className="flex flex-wrap gap-2">
                      <Link to="/comparar" className={buttonClass({ variant: "secondary", size: "sm" })}>
                        <Scale aria-hidden className="size-4" />{translate(" Ver onde compensa")}</Link>
                      {productId ? (
                        <Link to={`/produtos/${productId}`} className={buttonClass({ variant: "ghost", size: "sm" })}>{translate("Ajustar alerta")}</Link>
                      ) : null}
                      {!note.read_at ? (
                        <Button variant="ghost" size="sm" onClick={() => markRead.mutate([note.id])}>{translate("Marcar como lido")}</Button>
                      ) : null}
                    </div>
                  </Card>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState icon={BellRing} title={translate("Nenhum aviso ainda")}>{translate("Crie um alerta abaixo. Quando uma busca encontrar o produto pelo preço-alvo ou menos, ele aparece aqui.")}</EmptyState>
        )}
      </Section>

      <Section title={translate("Seus alertas de preço")} description={translate("O alvo vale por embalagem, por kg (itens vendidos a peso) ou por unidade. Só preços atuais, em estoque e não sinalizados disparam um aviso.")}>
        <NewAlertForm />
        {alerts.data?.length ? (
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {alerts.data.map((alert) => (
              <li key={alert.product_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <Link to={`/produtos/${alert.product_id}`} className="font-semibold hover:underline">
                    {alert.product_name}
                  </Link>
                  <p className="text-sm text-ink-3">{translate("Alvo ")}{translate(money(alert.target_price))}{translate(" por ")}{translate(alert.unit_label)}
                    {translate(alert.best_price ? ` · agora ${money(alert.best_price)} em ${alert.best_store}` : " · sem preço atual")}
                    {translate(alert.last_triggered_at ? ` · último aviso ${ago(alert.last_triggered_at)}` : "")}
                  </p>
                </div>
                {alert.enabled ? (
                  alert.best_price && Number(alert.best_price) <= Number(alert.target_price) ? (
                    <Badge tone="accent">{translate("No alvo")}</Badge>
                  ) : (
                    <Badge tone="brand">{translate("Ativo")}</Badge>
                  )
                ) : (
                  <Badge>{translate("Pausado")}</Badge>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-3">{translate("Nenhum alerta ainda. Escolha um produto da sua lista acima.")}</p>
        )}
      </Section>
    </div>
  );
}
