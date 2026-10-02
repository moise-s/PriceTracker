import { translate, useLocale } from "@/lib/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Store } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { keys } from "@/api/hooks";
import { Badge, Button, Card, Dialog, ErrorState, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow, Textarea } from "@/components/ui";
import { filterText, STATES } from "@/lib/markets";
import { MarketOnboarding } from "./market-onboarding";

type Market = Schemas["MarketAdminOut"];
type Branch = Schemas["StoreAdminOut"];
type Form = Record<"name" | "city" | "state" | "district" | "street" | "number" | "postal_code" | "external_id" | "seller" | "latitude" | "longitude", string> & { is_active: boolean };

function branchForm(store?: Branch): Form {
  return {
    name: store?.name ?? "", city: store?.city ?? "", state: store?.state ?? "",
    district: store?.district ?? "", street: store?.street ?? "", number: store?.number ?? "",
    postal_code: store?.postal_code ?? "", external_id: store?.external_id ?? "",
    seller: store?.seller ?? "", latitude: String(store?.latitude ?? ""),
    longitude: String(store?.longitude ?? ""), is_active: store?.is_active ?? true,
  };
}

export function AdminMarketsTab() {
  useLocale();
  const client = useQueryClient();
  const markets = useQuery({ queryKey: [...keys.admin, "markets"], queryFn: () => unwrap(api.GET("/api/v1/admin/markets")) });
  const [query, setQuery] = useState("");
  const [onboarding, setOnboarding] = useState(false);
  const [sourceMarket, setSourceMarket] = useState<Market | null>(null);
  const [editingMarket, setEditingMarket] = useState<Market | null>(null);
  const [marketForm, setMarketForm] = useState({ name: "", notes: "", brand_color: "#1BAF7A", enabled: true });
  const [editingStore, setEditingStore] = useState<{ market: Market; store?: Branch } | null>(null);
  const [form, setForm] = useState<Form>(() => branchForm());
  const invalidate = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: [...keys.admin, "markets"] }),
      client.invalidateQueries({ queryKey: keys.markets }),
      client.invalidateQueries({ queryKey: ["comparison"] }),
    ]);
  };
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["MarketPatch"] }) => unwrap(api.PATCH("/api/v1/admin/markets/{market_id}", { params: { path: { market_id: id } }, body })),
    onSuccess: async () => { await invalidate(); setEditingMarket(null); toast.success(translate("Mercado atualizado")); },
    onError: (e) => toast.error(translate(errorMessage(e))),
  });
  const save = useMutation({
    mutationFn: ({ marketId, storeId, body }: { marketId: string; storeId?: string; body: Schemas["StoreAdminIn"] }) => storeId
      ? unwrap(api.PUT("/api/v1/admin/markets/{market_id}/stores/{store_id}", { params: { path: { market_id: marketId, store_id: storeId } }, body }))
      : unwrap(api.POST("/api/v1/admin/markets/{market_id}/stores", { params: { path: { market_id: marketId } }, body })),
    onSuccess: async () => { await invalidate(); setEditingStore(null); toast.success(translate("Filial salva")); },
    onError: (e) => toast.error(translate(errorMessage(e))),
  });
  const change = (key: keyof Form, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));
  const openStore = (market: Market, store?: Branch) => { save.reset(); setForm(branchForm(store)); setEditingStore({ market, store }); };
  if (markets.isLoading) return <LoadingBlock label={translate("Carregando gestão de mercados")} />;
  if (markets.error || !markets.data) return <ErrorState error={translate("Não foi possível carregar os mercados.")} onRetry={() => void markets.refetch()} />;
  return (
    <div className="space-y-4">
      <InlineAlert title={translate("Configure as lojas da sua região")} tone="info">{translate("Estas configurações valem para todos nesta instalação. Cada pessoa escolhe suas lojas em ")}<Link className="underline" to="/mercados">{translate("Mercados")}</Link>{translate(". Use o assistente para testar e cadastrar uma rede nova com preços públicos online. ")}<Link className="underline" to="/ajuda">{translate("Veja como começar")}</Link>{translate(".")}</InlineAlert>
      <Button onClick={() => { setSourceMarket(null); setOnboarding(true); }}><Plus aria-hidden className="size-4" />{translate("Adicionar novo mercado")}</Button>
      {onboarding ? <MarketOnboarding market={sourceMarket} onClose={() => setOnboarding(false)} onCreated={invalidate} /> : null}
      <Field label={translate("Filtrar filiais por nome, cidade ou UF")} htmlFor="admin-store-filter">
        <Input id="admin-store-filter" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={translate("Ex.: Joinville, PR, Centro")} />
      </Field>
      {markets.data.map((market) => {
        const stores = market.stores.filter((s) => filterText(`${market.name} ${s.name} ${s.city} ${s.state}`).includes(filterText(query)));
        return (
          <Card key={market.id} as="section" className="min-w-0 space-y-3 p-4" aria-label={translate(`Gerenciar ${market.name}`)}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="flex flex-wrap items-center gap-2 font-bold"><Store aria-hidden className="size-5" />{market.name}<Badge tone={market.enabled ? "brand" : "neutral"}>{translate(market.enabled ? "Ativo" : "Desativado")}</Badge></h2>
              <div className="flex flex-wrap gap-2">
                {market.adapter_key === "public_jsonld" ? <Button variant="secondary" size="sm" onClick={() => { setSourceMarket(market); setOnboarding(true); }}>{translate("Revalidar fonte")}</Button> : null}
                <Button variant="secondary" size="sm" onClick={() => { patch.reset(); setEditingMarket(market); setMarketForm({ name: market.name, notes: market.notes ?? "", brand_color: market.brand_color ?? "#1BAF7A", enabled: market.enabled }); }}>{translate("Editar mercado")}</Button>
                <Button size="sm" disabled={market.context_kind === "unsupported"} onClick={() => openStore(market)}><Plus aria-hidden className="size-4" />{translate("Adicionar filial")}</Button>
              </div>
            </div>
            <p className="text-sm text-ink-2">{translate(market.context_help)}</p>
            {market.adapter_key === "public_jsonld" ? <p className="break-all text-sm text-ink-3">{translate("Fonte: ")}{translate(market.website)}{translate(" · índice: ")}{translate(market.sitemap_url)}</p> : null}
            <details>
              <summary className="cursor-pointer text-sm font-semibold">{translate(stores.length)}{translate(" de ")}{translate(market.stores.length)}{translate(" filiais · gerenciar lojas")}</summary>
              <ul className="mt-2 divide-y divide-line">
                {stores.map((store) => <li key={store.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div className="min-w-0"><p className="break-words font-semibold">{store.name} {!store.is_active ? <Badge>{translate("Desativada")}</Badge> : null}</p><p className="text-sm text-ink-3">{store.city}{translate("/")}{store.state}{translate(store.external_id ? ` · ID ${store.external_id}` : "")}</p></div>
                  <Button size="sm" variant="ghost" onClick={() => openStore(market, store)} aria-label={translate(`Editar filial ${store.name}`)}>{translate("Editar filial")}</Button>
                </li>)}
                {!stores.length ? <li className="py-3 text-sm text-ink-3">{translate("Nenhuma filial encontrada. Ajuste o filtro ou adicione uma loja.")}</li> : null}
              </ul>
            </details>
          </Card>
        );
      })}
      <Dialog open={Boolean(editingMarket)} onOpenChange={(o) => !o && !patch.isPending && setEditingMarket(null)} title={translate(`Editar mercado ${editingMarket?.name ?? ""}`)} footer={<><Button variant="ghost" disabled={patch.isPending} onClick={() => setEditingMarket(null)}>{translate("Cancelar")}</Button><Button type="submit" form="market-form" loading={patch.isPending}>{translate("Salvar mercado")}</Button></>}>
        <form id="market-form" className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (editingMarket) patch.mutate({ id: editingMarket.id, body: { ...marketForm, notes: marketForm.notes || null } }); }}>
          <Field label={translate("Nome do mercado")} htmlFor="market-name"><Input id="market-name" required minLength={2} maxLength={80} value={marketForm.name} onChange={(e) => setMarketForm((f) => ({ ...f, name: e.target.value }))} /></Field>
          <Field label={translate("Cor de identificação")} htmlFor="market-color"><Input id="market-color" type="color" value={marketForm.brand_color} onChange={(e) => setMarketForm((f) => ({ ...f, brand_color: e.target.value }))} /></Field>
          <Field label={translate("Notas sobre os preços")} htmlFor="market-notes"><Textarea id="market-notes" maxLength={1000} value={marketForm.notes} onChange={(e) => setMarketForm((f) => ({ ...f, notes: e.target.value }))} /></Field>
          <SwitchRow id="market-enabled" label={translate("Mercado disponível")} description={translate("Desativar retira todas as filiais das novas buscas e comparações. O histórico é preservado. Revise agendamentos que usam essas lojas.")} checked={marketForm.enabled} onCheckedChange={(v) => setMarketForm((f) => ({ ...f, enabled: v }))} />
          {patch.error ? <InlineAlert tone="danger" title={translate("Não foi possível salvar")}>{translate(errorMessage(patch.error))}</InlineAlert> : null}
        </form>
      </Dialog>
      <Dialog size="lg" open={Boolean(editingStore)} onOpenChange={(o) => !o && !save.isPending && setEditingStore(null)} title={translate(editingStore?.store ? `Editar filial ${editingStore.store.name}` : `Adicionar filial — ${editingStore?.market.name ?? ""}`)} footer={<><Button variant="ghost" disabled={save.isPending} onClick={() => setEditingStore(null)}>{translate("Cancelar")}</Button><Button type="submit" form="store-form" loading={save.isPending}>{translate("Salvar filial")}</Button></>}>
        <form id="store-form" className="space-y-4" onSubmit={(e) => {
          e.preventDefault();
          if (!editingStore) return;
          save.mutate({ marketId: editingStore.market.id, storeId: editingStore.store?.id, body: {
            ...form, external_id: form.external_id || null, seller: form.seller || null,
            postal_code: form.postal_code || null,
            latitude: form.latitude ? form.latitude.replace(",", ".") : null,
            longitude: form.longitude ? form.longitude.replace(",", ".") : null,
          } });
        }}>
          <InlineAlert tone={editingStore?.market.context_kind === "shared" ? "warn" : "info"} title={translate("Região de preços")}>{translate(editingStore?.market.context_help)}</InlineAlert>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label={translate("Nome da filial")} htmlFor="branch-name"><Input id="branch-name" required minLength={2} maxLength={120} value={form.name} onChange={(e) => change("name", e.target.value)} /></Field>
            <Field label={translate("Cidade")} htmlFor="branch-city"><Input id="branch-city" required minLength={2} maxLength={120} value={form.city} onChange={(e) => change("city", e.target.value)} /></Field>
            <Field label={translate("UF")} htmlFor="branch-state"><Select id="branch-state" required value={form.state} onChange={(e) => change("state", e.target.value)}><option value="">{translate("Selecione")}</option>{STATES.map((uf) => <option key={uf}>{uf}</option>)}</Select></Field>
            <Field label={translate("CEP da loja")} htmlFor="branch-cep"><Input id="branch-cep" inputMode="numeric" required={editingStore?.market.context_kind === "postal_code"} pattern="[0-9]{5}-?[0-9]{3}" maxLength={9} value={form.postal_code} onChange={(e) => change("postal_code", e.target.value)} placeholder={translate("00000-000")} /></Field>
            <Field label={translate("Bairro")} htmlFor="branch-district"><Input id="branch-district" maxLength={120} value={form.district} onChange={(e) => change("district", e.target.value)} /></Field>
            <Field label={translate("Rua")} htmlFor="branch-street"><Input id="branch-street" maxLength={200} value={form.street} onChange={(e) => change("street", e.target.value)} /></Field>
            <Field label={translate("Número")} htmlFor="branch-number"><Input id="branch-number" maxLength={20} value={form.number} onChange={(e) => change("number", e.target.value)} /></Field>
            {editingStore?.market.context_kind === "store_id" ? <Field label={translate("Identificador oficial da loja")} htmlFor="branch-id" hint={translate("Copie o ID usado pelo site da rede; não invente um número.")}><Input id="branch-id" required inputMode="numeric" pattern="[0-9]+" maxLength={80} value={form.external_id} onChange={(e) => change("external_id", e.target.value)} /></Field> : null}
            {editingStore?.market.context_kind === "postal_code" ? <Field label={translate("Vendedor da região (opcional)")} htmlFor="branch-seller"><Input id="branch-seller" maxLength={80} value={form.seller} onChange={(e) => change("seller", e.target.value)} /></Field> : null}
            <Field label={translate("Latitude (opcional)")} htmlFor="branch-lat" hint={translate("Para calcular distância. Informe as duas coordenadas.")}><Input id="branch-lat" inputMode="decimal" value={form.latitude} onChange={(e) => change("latitude", e.target.value)} placeholder={translate("-27,596900")} /></Field>
            <Field label={translate("Longitude (opcional)")} htmlFor="branch-lon"><Input id="branch-lon" inputMode="decimal" value={form.longitude} onChange={(e) => change("longitude", e.target.value)} placeholder={translate("-48,549500")} /></Field>
          </div>
          <SwitchRow id="branch-active" label={translate("Filial disponível")} description={translate("Desativar preserva o histórico e retira a loja das novas buscas e comparações. Revise seus agendamentos.")} checked={form.is_active} onCheckedChange={(v) => change("is_active", v)} />
          {save.error ? <InlineAlert tone="danger" title={translate("Confira os dados da filial")}>{translate(errorMessage(save.error))}</InlineAlert> : null}
        </form>
      </Dialog>
    </div>
  );
}
