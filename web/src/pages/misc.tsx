import { translate, useLocale } from "@/lib/i18n";
import { ArrowRight, Bell, CalendarClock, ChartLine, ChevronRight, CircleHelp, ListChecks, LogOut, MapPin, Shield, ShoppingBasket, Store, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { useLogout, useMe, useUpdateProfile } from "@/api/hooks";
import { Logo, PageHeader } from "@/app/shell";
import { Button, Card } from "@/components/ui";
import { buttonClass } from "@/components/ui/utils";

export function OnboardingPage() {
  useLocale();
  const me = useMe();
  const complete = useUpdateProfile();
  const navigate = useNavigate();
  const finish = (to: string) => complete.mutate({ complete_onboarding: true }, { onSettled: () => navigate(to) });
  const steps = [
    { icon: ShoppingBasket, title: "Monte sua lista", text: "Escolha no catálogo com fotos ou crie seus produtos, com quantidade e marca." },
    { icon: Store, title: "Escolha onde comparar", text: "Filtre as lojas por estado e cidade e marque as que você visita. O administrador pode cadastrar filiais das redes integradas." },
    { icon: MapPin, title: "Endereço e veículo (opcional)", text: "Para somar o custo de ida e volta. Você pode fazer isso depois." },
  ];
  return (
    <div className="mx-auto max-w-2xl py-6">
      <div className="mb-6"><Logo /></div>
      <PageHeader eyebrow={translate(`Bem-vindo, ${me.data?.user.display_name ?? ""}`)} title={translate("Vamos preparar sua primeira comparação")} description={translate("Leva poucos minutos. Só o essencial agora; o resto pode ser ajustado quando quiser.")} />
      <ol className="space-y-3">
        {steps.map((step, i) => (
          <li key={step.title}>
            <Card className="flex items-start gap-4 p-4">
              <span className="grid size-11 shrink-0 place-content-center rounded-xl bg-brand-soft text-brand"><step.icon aria-hidden className="size-5" /></span>
              <div>
                <p className="font-semibold">{translate(i + 1)}{translate(". ")}{step.title}</p>
                <p className="text-sm text-ink-2">{translate(step.text)}</p>
              </div>
            </Card>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex flex-wrap gap-2">
        <Button size="lg" onClick={() => finish("/lista")} loading={complete.isPending}>{translate("Começar pela lista ")}<ArrowRight aria-hidden className="size-5" />
        </Button>
        <Button size="lg" variant="ghost" onClick={() => finish("/")}>{translate("Pular por agora")}</Button>
        <Link to="/ajuda" className={buttonClass({ variant: "ghost", size: "lg" })}>{translate("Como usar")}</Link>
      </div>
    </div>
  );
}

export function MorePage() {
  useLocale();
  const me = useMe();
  const logout = useLogout();
  const items = [
    { to: "/mercados", label: "Mercados e lojas", icon: Store },
    { to: "/lista", label: "Minha lista", icon: ListChecks },
    { to: "/historico", label: "Histórico de preços", icon: ChartLine },
    { to: "/avisos", label: "Avisos e alertas de preço", icon: Bell },
    { to: "/agendamentos", label: "Agendamentos", icon: CalendarClock },
    { to: "/perfil", label: "Perfil, endereço e veículo", icon: UserRound },
    { to: "/ajuda", label: "Como usar e cobertura regional", icon: CircleHelp },
    ...(me.data?.user.role === "admin" ? [{ to: "/admin", label: "Administração", icon: Shield }] : []),
  ];
  return (
    <div className="space-y-4">
      <PageHeader title={translate("Mais")} />
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {items.map((item) => (
          <li key={item.to}>
            <Link to={item.to} className="flex items-center gap-3 px-4 py-3.5 font-semibold hover:bg-surface-2">
              <item.icon aria-hidden className="size-5 text-ink-3" /> <span className="flex-1">{translate(item.label)}</span> <ChevronRight aria-hidden className="size-4 text-ink-3" />
            </Link>
          </li>
        ))}
      </ul>
      <Button variant="secondary" className="w-full" onClick={() => logout.mutate()} loading={logout.isPending}>
        <LogOut aria-hidden className="size-4" />{translate(" Sair")}</Button>
    </div>
  );
}

export function NotFoundPage() {
  useLocale();
  return (
    <div className="py-16 text-center">
      <h1 className="text-3xl font-bold">{translate("Página não encontrada")}</h1>
      <p className="mt-2 text-ink-2">{translate("O endereço pode ter mudado.")}</p>
      <Link to="/" className={buttonClass({ className: "mt-6" })}>{translate("Ir para o início")}</Link>
    </div>
  );
}
