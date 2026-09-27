import { lazy, type ReactNode, Suspense } from "react";
import { createBrowserRouter, Navigate, useLocation } from "react-router";
import { useMe, useMeta } from "@/api/hooks";
import { AppShell, Logo } from "@/app/shell";
import { LoadingBlock, Spinner } from "@/components/ui";
import { ForcedPasswordChangePage, LoginPage, RecoverPage, RegisterPage, SetupPage } from "@/pages/auth";
import { HomePage } from "@/pages/home";
import { ListPage } from "@/pages/list";
import { MarketsPage } from "@/pages/markets";
import { MorePage, NotFoundPage, OnboardingPage } from "@/pages/misc";
import { RunPage, SearchPage } from "@/pages/search";

const AdminPage = lazy(() => import("@/pages/admin").then((m) => ({ default: m.AdminPage })));
const ComparePage = lazy(() => import("@/pages/compare").then((m) => ({ default: m.ComparePage })));
const HistoryPage = lazy(() => import("@/pages/history").then((m) => ({ default: m.HistoryPage })));
const ProductFormPage = lazy(() => import("@/pages/product-form").then((m) => ({ default: m.ProductFormPage })));
const ProfilePage = lazy(() => import("@/pages/profile").then((m) => ({ default: m.ProfilePage })));
const SchedulesPage = lazy(() => import("@/pages/schedules").then((m) => ({ default: m.SchedulesPage })));

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<LoadingBlock label="Carregando página" rows={3} />}>{children}</Suspense>;
}

function Splash() {
  return (
    <div className="grid min-h-dvh place-content-center gap-4 text-center">
      <Logo />
      <Spinner />
    </div>
  );
}

function RequireAuth({ children, allowPasswordChange = false }: { children: ReactNode; allowPasswordChange?: boolean }) {
  const meta = useMeta();
  const me = useMe();
  const location = useLocation();
  if (meta.isLoading || me.isLoading) return <Splash />;
  if (meta.data?.needs_setup) return <Navigate to="/configurar" replace />;
  if (!me.data) return <Navigate to="/entrar" replace state={{ from: location.pathname }} />;
  if (me.data.user.must_change_password && !allowPasswordChange) return <Navigate to="/trocar-senha" replace />;
  return <>{children}</>;
}

function PublicOnly({ children, setup = false }: { children: ReactNode; setup?: boolean }) {
  const meta = useMeta();
  const me = useMe();
  if (meta.isLoading || me.isLoading) return <Splash />;
  if (setup && !meta.data?.needs_setup) return <Navigate to={me.data ? "/" : "/entrar"} replace />;
  if (!setup && meta.data?.needs_setup) return <Navigate to="/configurar" replace />;
  if (!setup && me.data) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export const router = createBrowserRouter([
  { path: "/configurar", element: <PublicOnly setup><SetupPage /></PublicOnly> },
  { path: "/entrar", element: <PublicOnly><LoginPage /></PublicOnly> },
  { path: "/cadastro", element: <PublicOnly><RegisterPage /></PublicOnly> },
  { path: "/recuperar", element: <PublicOnly><RecoverPage /></PublicOnly> },
  { path: "/trocar-senha", element: <RequireAuth allowPasswordChange><ForcedPasswordChangePage /></RequireAuth> },
  { path: "/boas-vindas", element: <RequireAuth><OnboardingPage /></RequireAuth> },
  {
    path: "/",
    element: <RequireAuth><AppShell /></RequireAuth>,
    children: [
      { index: true, element: <HomePage /> },
      { path: "lista", element: <ListPage /> },
      { path: "produtos/novo", element: <Page><ProductFormPage /></Page> },
      { path: "produtos/:id", element: <Page><ProductFormPage /></Page> },
      { path: "mercados", element: <MarketsPage /> },
      { path: "buscar", element: <SearchPage /> },
      { path: "buscas/:id", element: <RunPage /> },
      { path: "comparar", element: <Page><ComparePage /></Page> },
      { path: "historico", element: <Page><HistoryPage /></Page> },
      { path: "agendamentos", element: <Page><SchedulesPage /></Page> },
      { path: "perfil", element: <Page><ProfilePage /></Page> },
      { path: "admin", element: <Page><AdminPage /></Page> },
      { path: "mais", element: <MorePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
