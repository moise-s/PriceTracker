import { translate, useLocale } from "@/lib/i18n";
import { type ReactNode, Suspense } from "react";
import { Navigate, useLocation } from "react-router";
import { useMe, useMeta } from "@/api/hooks";
import { Logo } from "@/app/shell";
import { LoadingBlock, Spinner } from "@/components/ui";

export function Page({ children }: { children: ReactNode }) {
  useLocale();
  return <Suspense fallback={<LoadingBlock label={translate("Carregando página")} rows={3} />}>{translate(children)}</Suspense>;
}

export function Splash() {
  useLocale();
  return (
    <div className="grid min-h-dvh place-content-center gap-4 text-center">
      <Logo />
      <Spinner />
    </div>
  );
}

/** Where a signed-in user belongs: onboarding first, then the app. Every guard agrees on this,
 * so racing redirects (e.g. right after first-access setup) always converge. */
function homeFor(me: { onboarding_completed: boolean }) {
  return me.onboarding_completed ? "/" : "/boas-vindas";
}

export function RequireAuth({ children, allowPasswordChange = false }: { children: ReactNode; allowPasswordChange?: boolean }) {
  useLocale();
  const meta = useMeta();
  const me = useMe();
  const location = useLocation();
  if (meta.isLoading || me.isLoading) return <Splash />;
  if (meta.data?.needs_setup) return <Navigate to="/configurar" replace />;
  if (!me.data) return <Navigate to="/entrar" replace state={{ from: location.pathname }} />;
  if (me.data.user.must_change_password && !allowPasswordChange) return <Navigate to="/trocar-senha" replace />;
  return <>{translate(children)}</>;
}

export function PublicOnly({ children, setup = false }: { children: ReactNode; setup?: boolean }) {
  useLocale();
  const meta = useMeta();
  const me = useMe();
  if (meta.isLoading || me.isLoading) return <Splash />;
  if (setup && !meta.data?.needs_setup) return <Navigate to={me.data ? homeFor(me.data) : "/entrar"} replace />;
  if (!setup && meta.data?.needs_setup) return <Navigate to="/configurar" replace />;
  if (!setup && me.data) return <Navigate to={homeFor(me.data)} replace />;
  return <>{translate(children)}</>;
}
