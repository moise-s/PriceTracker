import { translate, useLocale } from "@/lib/i18n";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { Button, Checkbox, Dialog, Field, InlineAlert, Input, Select } from "@/components/ui";
import { money } from "@/lib/format";
import { STATES } from "@/lib/markets";

export function MarketOnboarding({ market, onClose, onCreated }: { market?: Schemas["MarketAdminOut"] | null; onClose: () => void; onCreated: () => Promise<void> }) {
  useLocale();
  const [source, setSource] = useState({ website: market?.website ?? "", sample_url: "", sitemap_url: market?.sitemap_url ?? "" });
  const [form, setForm] = useState({ name: "", brand_color: "#1BAF7A", store_name: "", city: "", state: "" });
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<Schemas["MarketProbeOut"] | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const probe = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/admin/markets/probe", { body: { ...source, sitemap_url: source.sitemap_url || null } })),
    onSuccess: (data) => { setResult(data); if (data.supported) setStep(2); },
  });
  const create = useMutation({
    mutationFn: () => market ? unwrap(api.PUT("/api/v1/admin/markets/{market_id}/source", { params: { path: { market_id: market.id } }, body: { website: result!.website, sample_url: source.sample_url, sitemap_url: result!.sitemap_url, confirm_public_price: true } })) : unwrap(api.POST("/api/v1/admin/markets", { body: {
      website: result!.website, sample_url: source.sample_url, sitemap_url: result!.sitemap_url,
      name: form.name, brand_color: form.brand_color, confirm_public_price: true,
      first_store: { name: form.store_name, city: form.city, state: form.state, is_active: true },
    } })),
    onSuccess: async () => { await onCreated(); toast.success(translate(market ? "Fonte validada e atualizada" : "Mercado cadastrado e disponível para seleção")); onClose(); },
  });
  const busy = probe.isPending || create.isPending;
  const changeSource = (key: keyof typeof source, value: string) => {
    setSource((s) => ({ ...s, [key]: value })); setResult(null); setConfirmed(false); probe.reset(); create.reset();
  };
  return <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose(); }} size="lg" title={translate(market ? `Revalidar fonte — ${market.name}` : "Adicionar um novo mercado")} footer={<>
    <Button variant="ghost" disabled={busy} onClick={step === 2 ? () => { setStep(1); create.reset(); } : onClose}>{translate(step === 2 ? "Voltar ao site" : "Cancelar")}</Button>
    <Button type="submit" form="new-market-form" loading={busy} disabled={busy || (step === 2 && !confirmed)}>{step === 1 ? <><Search aria-hidden className="size-4" />{translate("Testar site")}</> : market ? "Salvar fonte validada" : "Cadastrar e ativar mercado"}</Button>
  </>}>
    <form id="new-market-form" className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (step === 1) probe.mutate(); else if (confirmed && result?.supported) create.mutate(); }}>
      <p className="text-sm font-semibold text-ink-3">{translate("Etapa ")}{translate(step)}{translate(" de 2 · ")}{translate(step === 1 ? "Testar a fonte de preços" : market ? "Revisar a fonte" : "Revisar e cadastrar a primeira loja")}</p>
      {step === 1 ? <>
        <InlineAlert title={translate(market ? "Teste novamente a fonte pública" : "Cadastre uma rede diferente das existentes")} tone="info">{translate("Cole o site e o link de um produto com preço público. O assistente verifica se consegue ler preços em reais e encontrar produtos automaticamente. Sites que exigem login, CEP ou carregam preços só por JavaScript podem precisar de integração própria.")}</InlineAlert>
        <Field label={translate("Site do mercado")} htmlFor="new-market-website" hint={translate(market ? "O domínio é preservado para manter a origem do histórico. Você pode atualizar o índice de produtos abaixo." : "Use o mesmo domínio que aparece ao abrir o produto. Ex.: https://loja.exemplo.com.br")}><Input id="new-market-website" required type="url" maxLength={200} placeholder={translate("https://")} value={source.website} onChange={(e) => changeSource("website", e.target.value)} readOnly={Boolean(market)} disabled={busy} /></Field>
        <Field label={translate("Link de um produto com preço")} htmlFor="new-market-sample" hint={translate("Abra o site sem login e copie uma página de produto, não a busca ou uma categoria.")}><Input id="new-market-sample" required type="url" maxLength={1000} placeholder={translate("https://loja.exemplo.com.br/arroz-1kg")} value={source.sample_url} onChange={(e) => changeSource("sample_url", e.target.value)} disabled={busy} /></Field>
        <details open={market ? true : undefined}><summary className="cursor-pointer text-sm font-semibold">{translate(market ? "Índice de produtos da rede" : "O site não encontra o índice automaticamente?")}</summary><div className="mt-3"><Field label={translate("Índice de produtos (opcional)")} htmlFor="new-market-sitemap" hint={translate("Link do sitemap XML no mesmo domínio. Geralmente fica em /sitemap.xml ou é informado em /robots.txt.")}><Input id="new-market-sitemap" type="url" maxLength={1000} placeholder={translate("https://loja.exemplo.com.br/sitemap.xml")} value={source.sitemap_url} onChange={(e) => changeSource("sitemap_url", e.target.value)} disabled={busy} /></Field></div></details>
        {probe.isPending ? <p role="status" className="text-sm text-ink-2">{translate("Verificando acesso, produto, preço e índice de páginas… Pode levar até 35 segundos.")}</p> : null}
        {probe.error ? <InlineAlert tone="danger" title={translate("Confira o endereço do site")}>{translate(errorMessage(probe.error))}</InlineAlert> : null}
        {result && !result.supported ? <InlineAlert tone="warn" title={translate("Este site ainda não está pronto para coleta")}>{translate(result.reason)}{translate(" Ajuste os links e teste novamente. Se o site não publica os dados necessários, é preciso implementar uma integração própria. ")}{translate(market ? "A configuração atual foi preservada." : "O mercado ainda não foi cadastrado.")}</InlineAlert> : null}
      </> : <>
        <InlineAlert tone="brand" title={translate(<span className="inline-flex items-center gap-2"><CheckCircle2 aria-hidden className="size-4" />{translate("Fonte reconhecida")}</span>)}>
          <p className="break-words font-semibold">{translate(result?.sample_name)}{translate(" · ")}{translate(money(result?.sample_price))}</p>
          <p className="mt-1 text-sm">{translate(result?.indexed_pages)}{translate(" páginas encontradas no índice. Isso confirma o exemplo, não a cobertura de todos os produtos; cada anúncio ainda precisa passar pelas regras de equivalência.")}</p>
        </InlineAlert>
        {!market ? <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label={translate("Nome da nova rede")} htmlFor="new-market-name"><Input id="new-market-name" required minLength={2} maxLength={80} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} disabled={busy} /></Field>
          <Field label={translate("Cor de identificação")} htmlFor="new-market-color"><Input id="new-market-color" type="color" value={form.brand_color} onChange={(e) => setForm((f) => ({ ...f, brand_color: e.target.value }))} disabled={busy} /></Field>
          <Field label={translate("Nome da primeira loja")} htmlFor="new-market-store"><Input id="new-market-store" required minLength={2} maxLength={120} placeholder={translate("Ex.: Centro")} value={form.store_name} onChange={(e) => setForm((f) => ({ ...f, store_name: e.target.value }))} disabled={busy} /></Field>
          <Field label={translate("Cidade")} htmlFor="new-market-city"><Input id="new-market-city" required minLength={2} maxLength={120} value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} disabled={busy} /></Field>
          <Field label={translate("UF")} htmlFor="new-market-state"><Select id="new-market-state" required value={form.state} onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))} disabled={busy}><option value="">{translate("Selecione")}</option>{STATES.map((uf) => <option key={uf}>{uf}</option>)}</Select></Field>
        </div> : <p className="text-sm text-ink-2">{translate("O índice validado será usado em todas as ")}{translate(market.stores.length)}{translate(" lojas desta rede. A disponibilidade de cada loja continua conforme o cadastro.")}</p>}
        <InlineAlert tone="warn" title={translate("Confirme a origem dos preços")}>{translate(result?.price_scope_note)}{translate(" Cadastros de filiais compartilham essa referência online; a cidade não configura uma região de preços. Após o cadastro, você pode completar o endereço e as coordenadas em Editar filial.")}</InlineAlert>
        <div className="flex items-start gap-3"><Checkbox id="new-market-confirm" checked={confirmed} disabled={busy} onCheckedChange={(v) => setConfirmed(v === true)} /><label htmlFor="new-market-confirm" className="text-sm">{translate("Conferi o preço de exemplo no site e aceito usar a referência online pública para estas lojas.")}</label></div>
        {create.isPending ? <p role="status" className="text-sm text-ink-2">{translate("Conferindo a fonte novamente e ")}{translate(market ? "salvando o índice" : "cadastrando o mercado")}{translate("…")}</p> : null}
        {create.error ? <InlineAlert tone="danger" title={translate(market ? "A fonte não foi atualizada" : "O mercado não foi cadastrado")}>{translate(errorMessage(create.error))}{translate(" Volte ao site para corrigir a fonte ou confira o nome da rede.")}</InlineAlert> : null}
      </>}
    </form>
  </Dialog>;
}
