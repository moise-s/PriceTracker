import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Copy, Download, KeyRound, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { z } from "zod";
import { api, ApiError, errorMessage, unwrap } from "@/api/client";
import { keys, useMeta } from "@/api/hooks";
import { AuthLayout } from "@/app/shell";
import { Button, Card, Field, InlineAlert, Input } from "@/components/ui";

const username = z
  .string()
  .trim()
  .toLowerCase()
  .regex(/^[a-z0-9][a-z0-9._-]{2,31}$/, "Use 3 a 32 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado.");
const password = z.string().min(10, "A senha precisa ter pelo menos 10 caracteres.").max(256);

export function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void | Promise<void> }) {
  const [confirmed, setConfirmed] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const text = codes.join("\n");
  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-11 shrink-0 place-content-center rounded-xl bg-accent-soft text-accent-ink">
          <KeyRound aria-hidden className="size-6" />
        </span>
        <div>
          <h1 className="text-2xl font-bold outline-none">Guarde seus códigos de recuperação</h1>
          <p className="mt-1 text-sm text-ink-2">
            Como não usamos e-mail, estes códigos permitem redefinir sua senha. Cada código funciona uma única vez e
            <strong> não será mostrado de novo</strong>.
          </p>
        </div>
      </div>
      <ol className="grid grid-cols-2 gap-2 rounded-lg bg-surface-2 p-4 font-mono text-[15px] tabular">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={() => void navigator.clipboard.writeText(text).then(() => toast.success("Códigos copiados"))}>
          <Copy aria-hidden className="size-4" /> Copiar
        </Button>
        <a
          className="inline-flex h-9 items-center gap-2 rounded-full px-3.5 text-sm font-semibold ring-1 ring-line-strong hover:bg-surface-2"
          href={`data:text/plain;charset=utf-8,${encodeURIComponent(`PriceTracker — códigos de recuperação\n\n${text}\n`)}`}
          download="pricetracker-codigos-de-recuperacao.txt"
        >
          <Download aria-hidden className="size-4" /> Baixar .txt
        </a>
      </div>
      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        Guardei os códigos em um lugar seguro
      </label>
      <Button
        className="w-full"
        disabled={!confirmed}
        loading={leaving}
        onClick={() => {
          setLeaving(true);
          void Promise.resolve(onDone()).finally(() => setLeaving(false));
        }}
      >
        Continuar
      </Button>
    </Card>
  );
}

const setupSchema = z
  .object({ username, display_name: z.string().trim().min(1, "Informe seu nome."), password, confirm: z.string(), setup_code: z.string().optional() })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "As senhas não conferem." });

export function SetupPage() {
  const meta = useMeta();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [codes, setCodes] = useState<string[] | null>(null);
  const form = useForm<z.infer<typeof setupSchema>>({ resolver: zodResolver(setupSchema), defaultValues: { username: "", display_name: "", password: "", confirm: "", setup_code: "" } });
  const [error, setError] = useState<string | null>(null);

  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await unwrap(
        api.POST("/api/v1/setup/admin", { body: { username: values.username, display_name: values.display_name, password: values.password, setup_code: values.setup_code || null } }),
      );
      setCodes(result.recovery_codes);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  if (codes) {
    return (
      <AuthLayout>
        <RecoveryCodes
          codes={codes}
          onDone={async () => {
            // Wait for fresh meta/me so the route guards don't act on the pre-setup cache.
            await Promise.all([client.invalidateQueries({ queryKey: keys.meta }), client.invalidateQueries({ queryKey: keys.me })]);
            navigate("/boas-vindas", { replace: true });
          }}
        />
      </AuthLayout>
    );
  }

  const requiresCode = meta.data?.requires_setup_code;
  const e = form.formState.errors;
  return (
    <AuthLayout>
      <Card className="p-6">
        <div className="mb-5 flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-content-center rounded-xl bg-brand-soft text-brand">
            <ShieldCheck aria-hidden className="size-6" />
          </span>
          <div>
            <h1 className="text-2xl font-bold outline-none">Primeiro acesso</h1>
            <p className="mt-1 text-sm text-ink-2">Crie a conta de administrador desta instalação. Não existe senha padrão.</p>
          </div>
        </div>
        {requiresCode ? (
          <InlineAlert tone="info" title="Código de configuração necessário">
            Para proteger a instalação, gere um código no servidor com <code className="rounded bg-surface px-1">pricetracker setup-code</code> e cole abaixo.
          </InlineAlert>
        ) : null}
        <form className="mt-4 space-y-4" onSubmit={submit} noValidate>
          {requiresCode ? (
            <Field label="Código de configuração" htmlFor="setup_code" error={e.setup_code?.message}>
              <Input id="setup_code" autoComplete="one-time-code" placeholder="XXXX-XXXX-XXXX" {...form.register("setup_code")} />
            </Field>
          ) : null}
          <Field label="Seu nome" htmlFor="display_name" error={e.display_name?.message}>
            <Input id="display_name" autoComplete="name" aria-invalid={Boolean(e.display_name)} {...form.register("display_name")} />
          </Field>
          <Field label="Nome de usuário" htmlFor="username" error={e.username?.message} hint="Usado para entrar. Ex.: ana.souza">
            <Input id="username" autoComplete="username" autoCapitalize="none" aria-invalid={Boolean(e.username)} {...form.register("username")} />
          </Field>
          <Field label="Senha" htmlFor="password" error={e.password?.message} hint="Pelo menos 10 caracteres.">
            <Input id="password" type="password" autoComplete="new-password" aria-invalid={Boolean(e.password)} {...form.register("password")} />
          </Field>
          <Field label="Confirme a senha" htmlFor="confirm" error={e.confirm?.message}>
            <Input id="confirm" type="password" autoComplete="new-password" aria-invalid={Boolean(e.confirm)} {...form.register("confirm")} />
          </Field>
          {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Criar administrador
          </Button>
        </form>
      </Card>
    </AuthLayout>
  );
}

const loginSchema = z.object({ username: z.string().trim().min(1, "Informe o usuário."), password: z.string().min(1, "Informe a senha.") });

export function LoginPage() {
  const meta = useMeta();
  const client = useQueryClient();
  const navigate = useNavigate();
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), defaultValues: { username: "", password: "" } });
  const [error, setError] = useState<string | null>(null);
  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const me = await unwrap(api.POST("/api/v1/auth/login", { body: values }));
      client.setQueryData(keys.me, me);
      navigate(me.user.must_change_password ? "/trocar-senha" : me.onboarding_completed ? "/" : "/boas-vindas", { replace: true });
    } catch (e) {
      setError(e instanceof ApiError && e.status === 429 ? e.message : errorMessage(e));
    }
  });
  const e = form.formState.errors;
  return (
    <AuthLayout>
      <Card className="p-6">
        <h1 className="text-2xl font-bold outline-none">Entrar</h1>
        <p className="mt-1 text-sm text-ink-2">Acesse sua lista e as comparações da semana.</p>
        <form className="mt-5 space-y-4" onSubmit={submit} noValidate>
          <Field label="Usuário" htmlFor="username" error={e.username?.message}>
            <Input id="username" autoComplete="username" autoCapitalize="none" aria-invalid={Boolean(e.username)} {...form.register("username")} />
          </Field>
          <Field label="Senha" htmlFor="password" error={e.password?.message}>
            <Input id="password" type="password" autoComplete="current-password" aria-invalid={Boolean(e.password)} {...form.register("password")} />
          </Field>
          {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Entrar
          </Button>
        </form>
        <div className="mt-5 flex flex-wrap justify-between gap-2 text-sm">
          <Link to="/recuperar" className="font-semibold text-brand hover:underline">
            Esqueci a senha
          </Link>
          {meta.data?.registration_enabled ? (
            <Link to="/cadastro" className="font-semibold text-brand hover:underline">
              Criar conta
            </Link>
          ) : null}
        </div>
      </Card>
    </AuthLayout>
  );
}

const registerSchema = z
  .object({ username, display_name: z.string().trim().min(1, "Informe seu nome."), password, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "As senhas não conferem." });

export function RegisterPage() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema), defaultValues: { username: "", display_name: "", password: "", confirm: "" } });
  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await unwrap(api.POST("/api/v1/auth/register", { body: { username: values.username, display_name: values.display_name, password: values.password } }));
      setCodes(result.recovery_codes);
    } catch (e) {
      setError(errorMessage(e));
    }
  });
  if (codes) {
    return (
      <AuthLayout>
        <RecoveryCodes codes={codes} onDone={async () => { await client.invalidateQueries({ queryKey: keys.me }); navigate("/boas-vindas", { replace: true }); }} />
      </AuthLayout>
    );
  }
  const e = form.formState.errors;
  return (
    <AuthLayout>
      <Card className="p-6">
        <h1 className="text-2xl font-bold outline-none">Criar conta</h1>
        <form className="mt-5 space-y-4" onSubmit={submit} noValidate>
          <Field label="Seu nome" htmlFor="display_name" error={e.display_name?.message}>
            <Input id="display_name" autoComplete="name" {...form.register("display_name")} />
          </Field>
          <Field label="Nome de usuário" htmlFor="username" error={e.username?.message}>
            <Input id="username" autoComplete="username" autoCapitalize="none" {...form.register("username")} />
          </Field>
          <Field label="Senha" htmlFor="password" error={e.password?.message}>
            <Input id="password" type="password" autoComplete="new-password" {...form.register("password")} />
          </Field>
          <Field label="Confirme a senha" htmlFor="confirm" error={e.confirm?.message}>
            <Input id="confirm" type="password" autoComplete="new-password" {...form.register("confirm")} />
          </Field>
          {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Criar conta
          </Button>
        </form>
        <p className="mt-4 text-center text-sm">
          <Link to="/entrar" className="font-semibold text-brand hover:underline">Já tenho conta</Link>
        </p>
      </Card>
    </AuthLayout>
  );
}

const recoverSchema = z
  .object({ username: z.string().trim().min(1, "Informe o usuário."), recovery_code: z.string().trim().min(6, "Informe um código."), new_password: password, confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "As senhas não conferem." });

export function RecoverPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof recoverSchema>>({ resolver: zodResolver(recoverSchema), defaultValues: { username: "", recovery_code: "", new_password: "", confirm: "" } });
  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await unwrap(api.POST("/api/v1/auth/recover", { body: { username: values.username, recovery_code: values.recovery_code, new_password: values.new_password } }));
      toast.success("Senha redefinida. Entre com a nova senha.");
      navigate("/entrar", { replace: true });
    } catch (e) {
      setError(errorMessage(e));
    }
  });
  const e = form.formState.errors;
  return (
    <AuthLayout>
      <Card className="p-6">
        <h1 className="text-2xl font-bold outline-none">Recuperar acesso</h1>
        <p className="mt-1 text-sm text-ink-2">Use um dos códigos de recuperação que você guardou. Sem código, peça ao administrador para redefinir sua senha.</p>
        <form className="mt-5 space-y-4" onSubmit={submit} noValidate>
          <Field label="Usuário" htmlFor="username" error={e.username?.message}>
            <Input id="username" autoComplete="username" autoCapitalize="none" {...form.register("username")} />
          </Field>
          <Field label="Código de recuperação" htmlFor="recovery_code" error={e.recovery_code?.message}>
            <Input id="recovery_code" autoComplete="one-time-code" placeholder="XXXXX-XXXXX" {...form.register("recovery_code")} />
          </Field>
          <Field label="Nova senha" htmlFor="new_password" error={e.new_password?.message}>
            <Input id="new_password" type="password" autoComplete="new-password" {...form.register("new_password")} />
          </Field>
          <Field label="Confirme a nova senha" htmlFor="confirm" error={e.confirm?.message}>
            <Input id="confirm" type="password" autoComplete="new-password" {...form.register("confirm")} />
          </Field>
          {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Redefinir senha
          </Button>
        </form>
        <p className="mt-4 text-center text-sm">
          <Link to="/entrar" className="font-semibold text-brand hover:underline">Voltar para entrar</Link>
        </p>
      </Card>
    </AuthLayout>
  );
}

const changeSchema = z
  .object({ current_password: z.string().min(1, "Informe a senha atual."), new_password: password, confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "As senhas não conferem." });

export function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof changeSchema>>({ resolver: zodResolver(changeSchema), defaultValues: { current_password: "", new_password: "", confirm: "" } });
  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await unwrap(api.POST("/api/v1/auth/change-password", { body: { current_password: values.current_password, new_password: values.new_password } }));
      toast.success("Senha alterada. As outras sessões foram encerradas.");
      form.reset();
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    }
  });
  const e = form.formState.errors;
  return (
    <form className="space-y-4" onSubmit={submit} noValidate>
      <Field label="Senha atual" htmlFor="current_password" error={e.current_password?.message}>
        <Input id="current_password" type="password" autoComplete="current-password" {...form.register("current_password")} />
      </Field>
      <Field label="Nova senha" htmlFor="new_password" error={e.new_password?.message}>
        <Input id="new_password" type="password" autoComplete="new-password" {...form.register("new_password")} />
      </Field>
      <Field label="Confirme a nova senha" htmlFor="confirm_new" error={e.confirm?.message}>
        <Input id="confirm_new" type="password" autoComplete="new-password" {...form.register("confirm")} />
      </Field>
      {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
      <Button type="submit" loading={form.formState.isSubmitting}>
        Alterar senha
      </Button>
    </form>
  );
}

export function ForcedPasswordChangePage() {
  const client = useQueryClient();
  const navigate = useNavigate();
  return (
    <AuthLayout>
      <Card className="p-6">
        <h1 className="text-2xl font-bold outline-none">Defina sua senha</h1>
        <p className="mt-1 mb-5 text-sm text-ink-2">Sua senha atual é temporária. Escolha uma nova para continuar.</p>
        <ChangePasswordForm
          onDone={() => {
            void client.invalidateQueries({ queryKey: keys.me });
            navigate("/", { replace: true });
          }}
        />
      </Card>
    </AuthLayout>
  );
}
