import {
  Bell,
  CalendarClock,
  ChartLine,
  Home,
  ListChecks,
  LogOut,
  Menu,
  Scale,
  Search,
  Settings2,
  Shield,
  Store,
  UserRound,
} from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useActiveRun, useLogout, useMe, useNotifications } from "@/api/hooks";
import { Button, Progress } from "@/components/ui";
import { setLocale, useLocale, translate } from "@/lib/i18n";
import { cn } from "@/components/ui/utils";

export function LanguageSwitcher() {
  const locale = useLocale();
  return <select aria-label={translate(locale === "en" ? "Language" : "Idioma")} value={locale} onChange={(event) => setLocale(event.target.value === "en" ? "en" : "pt-BR")} className="h-9 max-w-full rounded-lg border border-line bg-surface px-2 text-xs text-ink">
    <option value="pt-BR">{translate("Português (Brasil)")}</option><option value="en">{translate("English")}</option>
  </select>;
}

export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  useLocale();
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <svg viewBox="0 0 64 64" className="size-9 shrink-0" aria-hidden>
        <rect width="64" height="64" rx="16" fill="var(--color-brand)" />
        <path d="M17 27h30l-3.2 17.5A4 4 0 0 1 39.9 48H24.1a4 4 0 0 1-3.9-3.5Z" fill="#fff" />
        <path d="M23 27c0-6 4-10.5 9-10.5S41 21 41 27" fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round" />
        <path d="M27 34v7M32 34v7M37 34v7" stroke="var(--color-brand)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="46" cy="18" r="6" fill="var(--color-accent)" />
      </svg>
      {withText ? (
        <span className="leading-tight">
          <span className="block font-display text-[17px] font-bold tracking-tight text-ink">{translate("PriceTracker")}</span>
          <span className="block text-xs text-ink-3">{translate("onde a compra compensa")}</span>
        </span>
      ) : null}
    </span>
  );
}

type NavItem = { to: string; label: string; icon: typeof Home; end?: boolean };

const PRIMARY: NavItem[] = [
  { to: "/", label: "Início", icon: Home, end: true },
  { to: "/lista", label: "Minha lista", icon: ListChecks },
  { to: "/mercados", label: "Mercados", icon: Store },
  { to: "/buscar", label: "Buscar preços", icon: Search },
  { to: "/comparar", label: "Onde compensa", icon: Scale },
  { to: "/historico", label: "Histórico", icon: ChartLine },
  { to: "/avisos", label: "Avisos", icon: Bell },
  { to: "/agendamentos", label: "Agendamentos", icon: CalendarClock },
  { to: "/perfil", label: "Perfil", icon: UserRound },
];

const MOBILE: NavItem[] = [
  { to: "/", label: "Início", icon: Home, end: true },
  { to: "/lista", label: "Lista", icon: ListChecks },
  { to: "/buscar", label: "Buscar", icon: Search },
  { to: "/comparar", label: "Compensa", icon: Scale },
  { to: "/mais", label: "Mais", icon: Menu },
];

function UnreadBadge({ count, className }: { count: number; className?: string }) {
  useLocale();
  if (!count) return null;
  return <span aria-hidden className={cn("grid h-5 min-w-5 place-content-center rounded-full bg-accent px-1.5 text-[11px] font-bold text-on-accent tabular", className)}>{translate(count > 9 ? "9+" : count)}</span>;
}

function SideNav({ isAdmin }: { isAdmin: boolean }) {
  useLocale();
  const unread = useNotifications().data?.unread ?? 0;
  const items = isAdmin ? [...PRIMARY, { to: "/admin", label: "Administração", icon: Shield }] : PRIMARY;
  return (
    <nav aria-label={translate("Principal")} className="space-y-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-full px-4 py-2.5 text-[15px] font-semibold transition-colors",
              isActive ? "bg-brand text-on-brand shadow-card" : "text-ink-2 hover:bg-surface-3 hover:text-ink",
            )
          }
        >
          <item.icon aria-hidden className="size-5" />
          {translate(item.label)}
          {item.to === "/avisos" && unread ? (
            <>
              <span className="sr-only">{translate(", ")}{translate(unread)}{translate(" não lido")}{translate(unread > 1 ? "s" : "")}</span>
              <UnreadBadge count={unread} className="ml-auto" />
            </>
          ) : null}
        </NavLink>
      ))}
    </nav>
  );
}

function BottomNav() {
  useLocale();
  return (
    <nav aria-label={translate("Principal")} className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 px-2 pt-1.5 shadow-bar backdrop-blur lg:hidden">
      <ul className="mx-auto grid max-w-lg grid-cols-5">
        {MOBILE.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn("flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-[11px] font-semibold", isActive ? "text-brand" : "text-ink-3")
              }
            >
              {({ isActive }) => (
                <>
                  <span className={cn("grid h-8 w-12 place-content-center rounded-full transition-colors", item.to === "/buscar" ? (isActive ? "bg-brand text-on-brand" : "bg-brand-soft text-brand") : isActive ? "bg-brand-soft" : "")}>
                    <item.icon aria-hidden className="size-5" />
                  </span>
                  {translate(item.label)}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function ActiveRunBanner() {
  useLocale();
  const { data: run } = useActiveRun();
  const location = useLocation();
  if (!run || location.pathname.startsWith("/buscas/")) return null;
  return (
    <Link
      to={`/buscas/${run.id}`}
      className="fixed right-4 bottom-24 z-40 flex w-[min(20rem,calc(100vw-2rem))] items-center gap-3 rounded-2xl bg-ink px-4 py-3 text-canvas shadow-lift lg:bottom-6"
    >
      <Search aria-hidden className="size-5 shrink-0 animate-pulse" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{translate("Buscando preços…")}</span>
        <Progress value={run.done_targets} max={run.total_targets} label={translate("Progresso da busca")} className="mt-1.5 h-1.5 bg-white/20" />
      </span>
      <span className="text-xs tabular opacity-80">
        {translate(run.done_targets)}{translate("/")}{translate(run.total_targets)}
      </span>
    </Link>
  );
}

export function AppShell() {
  useLocale();
  const { data: me } = useMe();
  const unread = useNotifications().data?.unread ?? 0;
  const logout = useLogout();
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const heading = mainRef.current?.querySelector("h1");
    if (heading instanceof HTMLElement) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_1fr]">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-brand focus:px-4 focus:py-2 focus:text-on-brand">{translate("Pular para o conteúdo")}</a>
      {/* The column carries the background so it spans the whole page; the nav itself sticks. */}
      <div className="hidden border-r border-line bg-surface-2 lg:block">
        <aside className="sticky top-0 flex h-dvh flex-col px-4 py-6">
          <Link to="/" className="mb-8 px-2">
            <Logo />
          </Link>
          <SideNav isAdmin={me?.user.role === "admin"} />
          <div className="mt-auto mb-3"><LanguageSwitcher /></div>
          <div className="rounded-xl border border-line bg-surface p-3">
            <p className="truncate text-sm font-semibold">{me?.user.display_name}</p>
            <p className="truncate text-xs text-ink-3">{translate("@")}{me?.user.username}</p>
            <Button variant="ghost" size="sm" className="mt-2 w-full justify-start" onClick={() => logout.mutate()} loading={logout.isPending}>
              <LogOut aria-hidden className="size-4" />{translate("Sair")}</Button>
          </div>
        </aside>
      </div>
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-canvas/90 px-4 py-2.5 backdrop-blur lg:hidden">
          <Link to="/" aria-label={translate("Início")}>
            <Logo withText={false} />
          </Link>
          <div className="flex items-center gap-1">
            <LanguageSwitcher />
            <Link to="/avisos" className="relative grid size-10 place-content-center rounded-full text-ink-2 hover:bg-surface-3" aria-label={translate(unread ? `Avisos, ${unread} não lido${unread > 1 ? "s" : ""}` : "Avisos")}>
              <Bell aria-hidden className="size-5" />
              <UnreadBadge count={unread} className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 text-[10px]" />
            </Link>
            <Link to="/perfil" className="grid size-9 place-content-center rounded-full bg-brand-soft font-display text-sm font-bold text-brand-ink" aria-label={translate("Perfil")}>
              {me?.user.display_name?.slice(0, 1).toUpperCase() ?? <Settings2 className="size-4" />}
            </Link>
          </div>
        </header>
        <main id="conteudo" ref={mainRef} className="mx-auto w-full overflow-x-clip max-w-[84rem] px-4 pt-5 pb-32 sm:px-6 lg:px-8 lg:pt-10 lg:pb-16 xl:px-10">
          <Outlet />
        </main>
      </div>
      <ActiveRunBanner />
      <BottomNav />
    </div>
  );
}

export function PageHeader({ title, description, eyebrow, actions }: { title: ReactNode; description?: ReactNode; eyebrow?: ReactNode; actions?: ReactNode }) {
  useLocale();
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 animate-rise">
      <div className="min-w-0">
        {eyebrow ? <p className="mb-1 text-sm font-semibold text-brand">{translate(eyebrow)}</p> : null}
        <h1 className="text-[28px] leading-tight font-bold text-ink outline-none sm:text-[34px]">{translate(title)}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-[15px] text-ink-2">{translate(description)}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{translate(actions)}</div> : null}
    </div>
  );
}

export function AuthLayout({ children }: { children: ReactNode }) {
  useLocale();
  return (
    <div className="grid min-h-dvh place-items-center px-4 py-10">
      <main className="w-full max-w-md animate-rise">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="mb-5 flex justify-end"><LanguageSwitcher /></div>
        {translate(children)}
      </main>
    </div>
  );
}
