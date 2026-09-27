import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, KeyRound, PlugZap, Settings, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { keys } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { RecoveryCodes } from "@/pages/auth";
import { Badge, Button, Card, Dialog, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { ago, formatDateTime } from "@/lib/format";
import { HEALTH, METHOD, TARGET_STATUS } from "@/lib/labels";

function HealthTab() {
  const health = useQuery({ queryKey: [...keys.admin, "health"], queryFn: () => unwrap(api.GET("/api/v1/admin/health")) });
  if (health.isLoading || !health.data) return <LoadingBlock rows={2} />;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-3">Últimos 14 dias, agregados sem dados de usuários. IA: {health.data.llm.calls} chamadas ({health.data.llm.cache_hits} em cache, {health.data.llm.errors} com erro) em {health.data.llm.days} dias.</p>
      <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {health.data.markets.map((m) => {
          const state = HEALTH[m.state] ?? HEALTH.sem_dados!;
          return (
            <li key={m.market_id} className="min-w-0">
              <Card className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-lg font-bold">{m.name}</p>
                    <p className="text-xs break-words text-ink-3">
                      adaptador {m.adapter_version} · {m.strategy}
                    </p>
                  </div>
                  <Badge tone={state.tone}>{state.label}</Badge>
                </div>
                <dl className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <dt className="text-ink-3">Consultas</dt>
                    <dd className="font-bold tabular">{m.targets}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Sucesso</dt>
                    <dd className="font-bold tabular">{m.success_rate === null || m.success_rate === undefined ? "—" : `${Math.round(m.success_rate * 100)}%`}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Mediana</dt>
                    <dd className="font-bold tabular">{m.median_duration_ms ? `${(m.median_duration_ms / 1000).toFixed(1)} s` : "—"}</dd>
                  </div>
                </dl>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(m.statuses).map(([status, count]) => (
                    <Badge key={status} tone={TARGET_STATUS[status]?.tone ?? "neutral"}>
                      {TARGET_STATUS[status]?.label ?? status}: {count}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-ink-3">
                  Métodos: {Object.entries(m.methods).map(([k, v]) => `${METHOD[k] ?? k} (${v})`).join(", ") || "—"} · IA usada {m.llm_used}×, necessária {m.llm_needed}×
                </p>
                {Object.keys(m.errors).length ? <p className="text-xs text-danger">Erros: {Object.entries(m.errors).map(([k, v]) => `${k} (${v})`).join(", ")}</p> : null}
                <p className="text-xs text-ink-3">
                  Último sucesso {ago(m.last_success_at)} · última falha {ago(m.last_failure_at)}
                </p>
                {m.notes ? <p className="border-t border-line pt-2 text-xs text-ink-2">{m.notes}</p> : null}
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function LlmTab() {
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
    onError: (e) => toast.error(errorMessage(e)),
  });
  const save = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["LlmProviderIn"] }) => unwrap(api.PATCH("/api/v1/admin/llm-providers/{provider_id}", { params: { path: { provider_id: id } }, body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [...keys.admin, "llm"] });
      setEditing(null);
      setApiKey("");
      toast.success("Provedor atualizado");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!providers.data) return <LoadingBlock rows={2} />;
  return (
    <div className="space-y-4">
      <InlineAlert tone="info" title="A IA é só um fallback">
        Os adaptadores usam dados estruturados dos sites. A IA só é acionada quando essa leitura falha, recebe um trecho pequeno e tudo o que ela devolve é conferido. Chaves ficam no servidor (variáveis de ambiente) e nunca são exibidas. A assinatura do ChatGPT não inclui créditos de API: para OpenAI, use uma chave da plataforma de API.
      </InlineAlert>
      <ul className="space-y-3">
        {providers.data.map((p) => {
          const result = results[p.id];
          return (
            <li key={p.id}>
              <Card className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="flex items-center gap-2 text-lg font-bold">
                      <Bot aria-hidden className="size-5" /> {p.name} {p.is_default ? <Badge tone="brand">padrão</Badge> : null} {!p.enabled ? <Badge>desativado</Badge> : null}
                    </p>
                    <p className="text-sm text-ink-3">
                      Modelo <code>{p.model}</code> · saída {p.structured_output === "json_schema" ? "com schema estrito" : "JSON"}
                    </p>
                    <p className="text-sm text-ink-3">
                      Chave: {p.key_configured ? <Badge tone="brand" icon={KeyRound}>configurada ({p.key_source === "encrypted" ? "armazenada criptografada" : `variável ${p.key_env}`})</Badge> : <Badge tone="warn">não configurada</Badge>}
                    </p>
                    {p.last_check_at ? <p className="text-xs text-ink-3">Último teste {formatDateTime(p.last_check_at)}: {p.last_check_detail}</p> : null}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => { setEditing(p); setModel(p.model); }}>
                      Editar
                    </Button>
                    <Button size="sm" onClick={() => test.mutate(p.id)} loading={test.isPending && test.variables === p.id}>
                      <PlugZap aria-hidden className="size-4" /> Testar conexão
                    </Button>
                  </div>
                </div>
                {result ? (
                  <InlineAlert tone={result.ok ? "brand" : "danger"} title={result.ok ? "Conexão funcionando" : "Falha no teste"}>
                    {result.message}
                    {result.available_models?.length ? ` Modelos disponíveis: ${result.available_models.join(", ")}.` : ""}
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
        title={`Editar ${editing?.name ?? ""}`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancelar</Button>
            <Button onClick={() => editing && save.mutate({ id: editing.id, body: { model, ...(apiKey ? { api_key: apiKey } : {}) } })} loading={save.isPending}>Salvar</Button>
          </>
        }
      >
        {editing ? (
          <div className="space-y-4">
            <Field label="Modelo" htmlFor="llm_model" hint="Use “Testar conexão” para confirmar que o modelo existe no provedor.">
              <Input id="llm_model" value={model} onChange={(e) => setModel(e.target.value)} />
            </Field>
            <Field label="Chave de API (opcional)" htmlFor="llm_key" hint="Preferível: variável de ambiente no servidor. Se informada aqui, é criptografada e nunca volta pela API.">
              <Input id="llm_key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
            </Field>
            <SwitchRow id="llm_enabled" label="Ativo" checked={editing.enabled} onCheckedChange={(v) => save.mutate({ id: editing.id, body: { enabled: v } })} />
            <SwitchRow id="llm_default" label="Provedor padrão" checked={editing.is_default} onCheckedChange={(v) => save.mutate({ id: editing.id, body: { is_default: v } })} />
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}

function UsersTab() {
  const client = useQueryClient();
  const users = useQuery({ queryKey: [...keys.admin, "users"], queryFn: () => unwrap(api.GET("/api/v1/admin/users")) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Schemas["AdminUserIn"]>({ username: "", display_name: "", temporary_password: "", role: "user" });
  const [codes, setCodes] = useState<string[] | null>(null);
  const [reset, setReset] = useState<{ id: string; name: string } | null>(null);
  const [tempPassword, setTempPassword] = useState("");
  const invalidate = () => void client.invalidateQueries({ queryKey: [...keys.admin, "users"] });
  const create = useMutation({ mutationFn: (body: Schemas["AdminUserIn"]) => unwrap(api.POST("/api/v1/admin/users", { body })), onSuccess: (r) => { invalidate(); setCodes(r.recovery_codes); }, onError: (e) => toast.error(errorMessage(e)) });
  const patch = useMutation({ mutationFn: ({ id, body }: { id: string; body: Schemas["AdminUserPatch"] }) => unwrap(api.PATCH("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id } }, body })), onSuccess: invalidate, onError: (e) => toast.error(errorMessage(e)) });
  const resetPassword = useMutation({ mutationFn: ({ id, password }: { id: string; password: string }) => unwrap(api.POST("/api/v1/admin/users/{user_id}/reset-password", { params: { path: { user_id: id } }, body: { temporary_password: password } })), onSuccess: () => { setReset(null); setTempPassword(""); toast.success("Senha temporária definida; sessões encerradas."); }, onError: (e) => toast.error(errorMessage(e)) });
  return (
    <div className="space-y-4">
      <Button onClick={() => { setForm({ username: "", display_name: "", temporary_password: "", role: "user" }); setCodes(null); setOpen(true); }}>
        <UserPlus aria-hidden className="size-4" /> Criar usuário
      </Button>
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {(users.data ?? []).map((u) => (
          <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
            <span>
              <span className="font-semibold">{u.display_name}</span> <span className="text-ink-3">@{u.username}</span> {u.role === "admin" ? <Badge tone="info">admin</Badge> : null} {!u.is_active ? <Badge tone="danger">desativado</Badge> : null} {u.must_change_password ? <Badge tone="warn">senha temporária</Badge> : null}
              <span className="block text-xs text-ink-3">último acesso {ago(u.last_login_at)}</span>
            </span>
            <span className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => setReset({ id: u.id, name: u.display_name })}>Redefinir senha</Button>
              <Button variant="ghost" size="sm" onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>{u.is_active ? "Desativar" : "Reativar"}</Button>
            </span>
          </li>
        ))}
      </ul>
      <Dialog open={open} onOpenChange={setOpen} title="Criar usuário" description={codes ? undefined : "O usuário troca a senha temporária no primeiro acesso."}>
        {codes ? (
          <RecoveryCodes codes={codes} onDone={() => setOpen(false)} />
        ) : (
          <div className="space-y-3">
            <Field label="Nome" htmlFor="u_name"><Input id="u_name" value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} /></Field>
            <Field label="Usuário" htmlFor="u_username"><Input id="u_username" autoCapitalize="none" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} /></Field>
            <Field label="Senha temporária" htmlFor="u_password" hint="Pelo menos 10 caracteres."><Input id="u_password" type="password" autoComplete="new-password" value={form.temporary_password} onChange={(e) => setForm((f) => ({ ...f, temporary_password: e.target.value }))} /></Field>
            <Field label="Papel" htmlFor="u_role"><Select id="u_role" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as "user" | "admin" }))}><option value="user">Usuário</option><option value="admin">Administrador</option></Select></Field>
            <Button onClick={() => create.mutate(form)} loading={create.isPending}>Criar</Button>
          </div>
        )}
      </Dialog>
      <Dialog open={Boolean(reset)} onOpenChange={(o) => !o && setReset(null)} title={`Redefinir senha de ${reset?.name ?? ""}`} description="Define uma senha temporária e encerra as sessões do usuário.">
        <div className="space-y-3">
          <Field label="Senha temporária" htmlFor="reset_pw"><Input id="reset_pw" type="password" autoComplete="new-password" value={tempPassword} onChange={(e) => setTempPassword(e.target.value)} /></Field>
          <Button onClick={() => reset && resetPassword.mutate({ id: reset.id, password: tempPassword })} loading={resetPassword.isPending} disabled={tempPassword.length < 10}>Redefinir</Button>
        </div>
      </Dialog>
    </div>
  );
}

function SettingsTab() {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: [...keys.admin, "settings"], queryFn: () => unwrap(api.GET("/api/v1/admin/settings")) });
  const patch = useMutation({ mutationFn: (body: Schemas["AdminSettingsPatch"]) => unwrap(api.PATCH("/api/v1/admin/settings", { body })), onSuccess: () => { void client.invalidateQueries({ queryKey: [...keys.admin, "settings"] }); void client.invalidateQueries({ queryKey: keys.meta }); toast.success("Configuração salva"); }, onError: (e) => toast.error(errorMessage(e)) });
  if (!settings.data) return <LoadingBlock rows={1} />;
  const s = settings.data;
  return (
    <Card className="space-y-2 p-5">
      <SwitchRow id="registration" label="Permitir autocadastro" description="Desligado por padrão em instalações domésticas: o administrador cria as contas." checked={s.registration_enabled} onCheckedChange={(v) => patch.mutate({ registration_enabled: v })} />
      <SwitchRow id="llm_global" label="Permitir fallback por IA" description="Se desligado, alvos que precisariam de IA ficam marcados como “Precisa de IA”." checked={s.llm_enabled} onCheckedChange={(v) => patch.mutate({ llm_enabled: v })} />
      <div className="grid gap-4 pt-2 sm:grid-cols-2">
        <Field label="Frescor padrão (dias) para novas contas" htmlFor="default_freshness">
          <Select id="default_freshness" value={s.default_freshness_days} onChange={(e) => patch.mutate({ default_freshness_days: Number(e.target.value) })}>
            {[3, 5, 7, 10, 14].map((d) => <option key={d} value={d}>{d} dias</option>)}
          </Select>
        </Field>
        <Field label="Limite de chamadas de IA por busca" htmlFor="llm_budget">
          <Select id="llm_budget" value={s.llm_max_calls_per_run} onChange={(e) => patch.mutate({ llm_max_calls_per_run: Number(e.target.value) })}>
            {[0, 5, 12, 25, 50].map((d) => <option key={d} value={d}>{d}</option>)}
          </Select>
        </Field>
      </div>
    </Card>
  );
}

export function AdminPage() {
  return (
    <div className="space-y-5">
      <PageHeader title="Administração" description="Saúde das fontes, provedores de IA, usuários e configurações da instalação." />
      <Tabs defaultValue="saude" className="space-y-4">
        <TabsList aria-label="Seções da administração" className="w-fit max-w-full">
          <TabsTrigger value="saude"><Activity aria-hidden className="mr-1.5 inline size-4" />Fontes</TabsTrigger>
          <TabsTrigger value="ia"><Bot aria-hidden className="mr-1.5 inline size-4" />IA</TabsTrigger>
          <TabsTrigger value="usuarios"><Users aria-hidden className="mr-1.5 inline size-4" />Usuários</TabsTrigger>
          <TabsTrigger value="config"><Settings aria-hidden className="mr-1.5 inline size-4" />Configurações</TabsTrigger>
        </TabsList>
        <TabsContent value="saude"><HealthTab /></TabsContent>
        <TabsContent value="ia"><LlmTab /></TabsContent>
        <TabsContent value="usuarios"><UsersTab /></TabsContent>
        <TabsContent value="config"><SettingsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
