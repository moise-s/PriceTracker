import { translate, useLocale } from "@/lib/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, KeyRound, PlugZap, Settings, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { keys } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { RecoveryCodes } from "@/pages/auth";
import { AdminMarketsTab } from "@/pages/admin-markets";
import { Badge, Button, Card, Dialog, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { ago, formatDateTime } from "@/lib/format";
import { HEALTH, METHOD, TARGET_STATUS } from "@/lib/labels";

function HealthTab() {
  useLocale();
  const health = useQuery({ queryKey: [...keys.admin, "health"], queryFn: () => unwrap(api.GET("/api/v1/admin/health")) });
  if (health.isLoading || !health.data) return <LoadingBlock rows={2} />;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-3">{translate("Últimos 14 dias, agregados sem dados de usuários. IA: ")}{translate(health.data.llm.calls)}{translate(" chamadas (")}{translate(health.data.llm.cache_hits)}{translate(" em cache, ")}{translate(health.data.llm.errors)}{translate(" com erro) em ")}{translate(health.data.llm.days)}{translate(" dias.")}</p>
      <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {health.data.markets.map((m) => {
          const state = HEALTH[m.state] ?? HEALTH.sem_dados!;
          return (
            <li key={m.market_id} className="min-w-0">
              <Card className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-lg font-bold">{m.name}</p>
                    <p className="text-xs break-words text-ink-3">{translate("adaptador ")}{translate(m.adapter_version)}{translate(" · ")}{translate(m.strategy)}
                    </p>
                  </div>
                  <Badge tone={state.tone}>{translate(state.label)}</Badge>
                </div>
                <dl className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <dt className="text-ink-3">{translate("Consultas")}</dt>
                    <dd className="font-bold tabular">{translate(m.targets)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">{translate("Sucesso")}</dt>
                    <dd className="font-bold tabular">{translate(m.success_rate === null || m.success_rate === undefined ? "—" : `${Math.round(m.success_rate * 100)}%`)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">{translate("Mediana")}</dt>
                    <dd className="font-bold tabular">{translate(m.median_duration_ms ? `${(m.median_duration_ms / 1000).toFixed(1)} s` : "—")}</dd>
                  </div>
                </dl>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(m.statuses).map(([status, count]) => (
                    <Badge key={status} tone={TARGET_STATUS[status]?.tone ?? "neutral"}>
                      {translate(TARGET_STATUS[status]?.label ?? status)}{translate(": ")}{translate(count)}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-ink-3">{translate("Métodos: ")}{translate(Object.entries(m.methods).map(([k, v]) => `${METHOD[k] ?? k} (${v})`).join(", ") || "—")}{translate(" · IA usada ")}{translate(m.llm_used)}{translate("×, necessária ")}{translate(m.llm_needed)}{translate("×")}</p>
                {Object.keys(m.errors).length ? <p className="text-xs text-danger">{translate("Erros: ")}{translate(Object.entries(m.errors).map(([k, v]) => `${k} (${v})`).join(", "))}</p> : null}
                <p className="text-xs text-ink-3">{translate("Último sucesso ")}{translate(ago(m.last_success_at))}{translate(" · última falha ")}{translate(ago(m.last_failure_at))}
                </p>
                {m.notes ? <p className="border-t border-line pt-2 text-xs text-ink-2">{translate(m.notes)}</p> : null}
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function LlmTab() {
  useLocale();
  const client = useQueryClient();
  const providers = useQuery({ queryKey: [...keys.admin, "llm"], queryFn: () => unwrap(api.GET("/api/v1/admin/llm-providers")) });
  const [results, setResults] = useState<Record<string, Schemas["LlmTestOut"]>>({});
  const [editing, setEditing] = useState<Schemas["LlmProviderOut"] | null>(null);
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const test = useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/admin/llm-providers/{provider_id}/test", { params: { path: { provider_id: id } } })),
    onSuccess: (result, id) => {
      setResults((r) => ({ ...r, [id]: result }));
      void client.invalidateQueries({ queryKey: [...keys.admin, "llm"] });
    },
    onError: (e) => toast.error(translate(errorMessage(e))),
  });
  const save = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["LlmProviderIn"] }) => unwrap(api.PATCH("/api/v1/admin/llm-providers/{provider_id}", { params: { path: { provider_id: id } }, body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [...keys.admin, "llm"] });
      setEditing(null);
      setApiKey("");
      toast.success(translate("Provedor atualizado"));
    },
    onError: (e) => toast.error(translate(errorMessage(e))),
  });
  if (!providers.data) return <LoadingBlock rows={2} />;
  return (
    <div className="space-y-4">
      <InlineAlert tone="info" title={translate("A IA é só um fallback")}>{translate("Os adaptadores usam dados estruturados dos sites. A IA só é acionada quando essa leitura falha, recebe um trecho pequeno e tudo o que ela devolve é conferido. Chaves ficam no servidor (variáveis de ambiente) e nunca são exibidas. A assinatura do ChatGPT não inclui créditos de API: para OpenAI, use uma chave da plataforma de API.")}</InlineAlert>
      <ul className="space-y-3">
        {providers.data.map((p) => {
          const result = results[p.id];
          return (
            <li key={p.id}>
              <Card className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="flex items-center gap-2 text-lg font-bold">
                      <Bot aria-hidden className="size-5" /> {p.name} {p.is_default ? <Badge tone="brand">{translate("padrão")}</Badge> : null} {!p.enabled ? <Badge>{translate("desativado")}</Badge> : null}
                    </p>
                    <p className="text-sm text-ink-3">{translate("Modelo ")}<code>{translate(p.model)}</code>{translate(" · saída ")}{translate(p.structured_output === "json_schema" ? "com schema estrito" : "JSON")}
                    </p>
                    <p className="text-sm text-ink-3">{translate("Chave: ")}{p.key_configured ? <Badge tone="brand" icon={KeyRound}>{translate("configurada (")}{translate(p.key_source === "encrypted" ? "armazenada criptografada" : `variável ${p.key_env}`)}{translate(")")}</Badge> : <Badge tone="warn">{translate("não configurada")}</Badge>}
                    </p>
                    {p.last_check_at ? <p className="text-xs text-ink-3">{translate("Último teste ")}{translate(formatDateTime(p.last_check_at))}{translate(": ")}{translate(p.last_check_detail)}</p> : null}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => { setEditing(p); setModel(p.model); }}>{translate("Editar")}</Button>
                    <Button size="sm" onClick={() => test.mutate(p.id)} loading={test.isPending && test.variables === p.id}>
                      <PlugZap aria-hidden className="size-4" />{translate(" Testar conexão")}</Button>
                  </div>
                </div>
                {result ? (
                  <InlineAlert tone={result.ok ? "brand" : "danger"} title={translate(result.ok ? "Conexão funcionando" : "Falha no teste")}>
                    {translate(result.message)}
                    {translate(result.available_models?.length ? ` Modelos disponíveis: ${result.available_models.join(", ")}.` : "")}
                  </InlineAlert>
                ) : null}
              </Card>
            </li>
          );
        })}
      </ul>
      <Dialog
        open={Boolean(editing)}
        onOpenChange={(open) => !open && setEditing(null)}
        title={translate(`Editar ${editing?.name ?? ""}`)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>{translate("Cancelar")}</Button>
            <Button onClick={() => editing && save.mutate({ id: editing.id, body: { model, ...(apiKey ? { api_key: apiKey } : {}) } })} loading={save.isPending}>{translate("Salvar")}</Button>
          </>
        }
      >
        {editing ? (
          <div className="space-y-4">
            <Field label={translate("Modelo")} htmlFor="llm_model" hint={translate("Use “Testar conexão” para confirmar que o modelo existe no provedor.")}>
              <Input id="llm_model" value={model} onChange={(e) => setModel(e.target.value)} />
            </Field>
            <Field label={translate("Chave de API (opcional)")} htmlFor="llm_key" hint={translate("Preferível: variável de ambiente no servidor. Se informada aqui, é criptografada e nunca volta pela API.")}>
              <Input id="llm_key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
            </Field>
            <SwitchRow id="llm_enabled" label={translate("Ativo")} checked={editing.enabled} onCheckedChange={(v) => save.mutate({ id: editing.id, body: { enabled: v } })} />
            <SwitchRow id="llm_default" label={translate("Provedor padrão")} checked={editing.is_default} onCheckedChange={(v) => save.mutate({ id: editing.id, body: { is_default: v } })} />
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}

function UsersTab() {
  useLocale();
  const client = useQueryClient();
  const users = useQuery({ queryKey: [...keys.admin, "users"], queryFn: () => unwrap(api.GET("/api/v1/admin/users")) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Schemas["AdminUserIn"]>({ username: "", display_name: "", temporary_password: "", role: "user" });
  const [codes, setCodes] = useState<string[] | null>(null);
  const [reset, setReset] = useState<{ id: string; name: string } | null>(null);
  const [tempPassword, setTempPassword] = useState("");
  const invalidate = () => void client.invalidateQueries({ queryKey: [...keys.admin, "users"] });
  const create = useMutation({ mutationFn: (body: Schemas["AdminUserIn"]) => unwrap(api.POST("/api/v1/admin/users", { body })), onSuccess: (r) => { invalidate(); setCodes(r.recovery_codes); }, onError: (e) => toast.error(translate(errorMessage(e))) });
  const patch = useMutation({ mutationFn: ({ id, body }: { id: string; body: Schemas["AdminUserPatch"] }) => unwrap(api.PATCH("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id } }, body })), onSuccess: invalidate, onError: (e) => toast.error(translate(errorMessage(e))) });
  const resetPassword = useMutation({ mutationFn: ({ id, password }: { id: string; password: string }) => unwrap(api.POST("/api/v1/admin/users/{user_id}/reset-password", { params: { path: { user_id: id } }, body: { temporary_password: password } })), onSuccess: () => { setReset(null); setTempPassword(""); toast.success(translate("Senha temporária definida; sessões encerradas.")); }, onError: (e) => toast.error(translate(errorMessage(e))) });
  return (
    <div className="space-y-4">
      <Button onClick={() => { setForm({ username: "", display_name: "", temporary_password: "", role: "user" }); setCodes(null); setOpen(true); }}>
        <UserPlus aria-hidden className="size-4" />{translate(" Criar usuário")}</Button>
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {(users.data ?? []).map((u) => (
          <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
            <span>
              <span className="font-semibold">{u.display_name}</span> <span className="text-ink-3">{translate("@")}{u.username}</span> {u.role === "admin" ? <Badge tone="info">{translate("admin")}</Badge> : null} {!u.is_active ? <Badge tone="danger">{translate("desativado")}</Badge> : null} {u.must_change_password ? <Badge tone="warn">{translate("senha temporária")}</Badge> : null}
              <span className="block text-xs text-ink-3">{translate("último acesso ")}{translate(ago(u.last_login_at))}</span>
            </span>
            <span className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => setReset({ id: u.id, name: u.display_name })}>{translate("Redefinir senha")}</Button>
              <Button variant="ghost" size="sm" onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>{translate(u.is_active ? "Desativar" : "Reativar")}</Button>
            </span>
          </li>
        ))}
      </ul>
      <Dialog open={open} onOpenChange={setOpen} title={translate("Criar usuário")} description={translate(codes ? undefined : "O usuário troca a senha temporária no primeiro acesso.")}>
        {codes ? (
          <RecoveryCodes codes={codes} onDone={() => setOpen(false)} />
        ) : (
          <div className="space-y-3">
            <Field label={translate("Nome")} htmlFor="u_name"><Input id="u_name" value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} /></Field>
            <Field label={translate("Usuário")} htmlFor="u_username"><Input id="u_username" autoCapitalize="none" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} /></Field>
            <Field label={translate("Senha temporária")} htmlFor="u_password" hint={translate("Pelo menos 10 caracteres.")}><Input id="u_password" type="password" autoComplete="new-password" value={form.temporary_password} onChange={(e) => setForm((f) => ({ ...f, temporary_password: e.target.value }))} /></Field>
            <Field label={translate("Papel")} htmlFor="u_role"><Select id="u_role" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as "user" | "admin" }))}><option value="user">{translate("Usuário")}</option><option value="admin">{translate("Administrador")}</option></Select></Field>
            <Button onClick={() => create.mutate(form)} loading={create.isPending}>{translate("Criar")}</Button>
          </div>
        )}
      </Dialog>
      <Dialog open={Boolean(reset)} onOpenChange={(o) => !o && setReset(null)} title={translate(`Redefinir senha de ${reset?.name ?? ""}`)} description={translate("Define uma senha temporária e encerra as sessões do usuário.")}>
        <div className="space-y-3">
          <Field label={translate("Senha temporária")} htmlFor="reset_pw"><Input id="reset_pw" type="password" autoComplete="new-password" value={tempPassword} onChange={(e) => setTempPassword(e.target.value)} /></Field>
          <Button onClick={() => reset && resetPassword.mutate({ id: reset.id, password: tempPassword })} loading={resetPassword.isPending} disabled={tempPassword.length < 10}>{translate("Redefinir")}</Button>
        </div>
      </Dialog>
    </div>
  );
}

function SettingsTab() {
  useLocale();
  const client = useQueryClient();
  const settings = useQuery({ queryKey: [...keys.admin, "settings"], queryFn: () => unwrap(api.GET("/api/v1/admin/settings")) });
  const patch = useMutation({ mutationFn: (body: Schemas["AdminSettingsPatch"]) => unwrap(api.PATCH("/api/v1/admin/settings", { body })), onSuccess: () => { void client.invalidateQueries({ queryKey: [...keys.admin, "settings"] }); void client.invalidateQueries({ queryKey: keys.meta }); toast.success(translate("Configuração salva")); }, onError: (e) => toast.error(translate(errorMessage(e))) });
  if (!settings.data) return <LoadingBlock rows={1} />;
  const s = settings.data;
  return (
    <Card className="space-y-2 p-5">
      <SwitchRow id="registration" label={translate("Permitir autocadastro")} description={translate("Desligado por padrão em instalações domésticas: o administrador cria as contas.")} checked={s.registration_enabled} onCheckedChange={(v) => patch.mutate({ registration_enabled: v })} />
      <SwitchRow id="llm_global" label={translate("Permitir fallback por IA")} description={translate("Se desligado, alvos que precisariam de IA ficam marcados como “Precisa de IA”.")} checked={s.llm_enabled} onCheckedChange={(v) => patch.mutate({ llm_enabled: v })} />
      <div className="grid gap-4 pt-2 sm:grid-cols-2">
        <Field label={translate("Frescor padrão (dias) para novas contas")} htmlFor="default_freshness">
          <Select id="default_freshness" value={s.default_freshness_days} onChange={(e) => patch.mutate({ default_freshness_days: Number(e.target.value) })}>
            {[3, 5, 7, 10, 14].map((d) => <option key={d} value={d}>{translate(d)}{translate(" dias")}</option>)}
          </Select>
        </Field>
        <Field label={translate("Limite de chamadas de IA por busca")} htmlFor="llm_budget">
          <Select id="llm_budget" value={s.llm_max_calls_per_run} onChange={(e) => patch.mutate({ llm_max_calls_per_run: Number(e.target.value) })}>
            {[0, 5, 12, 25, 50].map((d) => <option key={d} value={d}>{translate(d)}</option>)}
          </Select>
        </Field>
      </div>
    </Card>
  );
}

export function AdminPage() {
  useLocale();
  return (
    <div className="space-y-5">
      <PageHeader title={translate("Administração")} description={translate("Mercados e filiais, saúde das fontes, usuários e configurações da instalação.")} />
      <Tabs defaultValue="saude" className="space-y-4">
        <TabsList aria-label={translate("Seções da administração")} className="w-fit max-w-full">
          <TabsTrigger value="mercados">{translate("Mercados")}</TabsTrigger>
          <TabsTrigger value="saude"><Activity aria-hidden className="mr-1.5 inline size-4" />{translate("Fontes")}</TabsTrigger>
          <TabsTrigger value="ia"><Bot aria-hidden className="mr-1.5 inline size-4" />{translate("IA")}</TabsTrigger>
          <TabsTrigger value="usuarios"><Users aria-hidden className="mr-1.5 inline size-4" />{translate("Usuários")}</TabsTrigger>
          <TabsTrigger value="config"><Settings aria-hidden className="mr-1.5 inline size-4" />{translate("Configurações")}</TabsTrigger>
        </TabsList>
        <TabsContent value="mercados"><AdminMarketsTab /></TabsContent>
        <TabsContent value="saude"><HealthTab /></TabsContent>
        <TabsContent value="ia"><LlmTab /></TabsContent>
        <TabsContent value="usuarios"><UsersTab /></TabsContent>
        <TabsContent value="config"><SettingsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
