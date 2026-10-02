import { createBrowserRouter } from "react-router";
import { Page, PublicOnly, RequireAuth } from "@/app/guards";
import { AdminPage, ComparePage, HistoryPage, NotificationsPage, ProductFormPage, ProfilePage, SchedulesPage } from "@/app/lazy-pages";
import { AppShell } from "@/app/shell";
import { ForcedPasswordChangePage, LoginPage, RecoverPage, RegisterPage, SetupPage } from "@/pages/auth";
import { HomePage } from "@/pages/home";
import { HelpPage } from "@/pages/help";
import { ListPage } from "@/pages/list";
import { MarketsPage } from "@/pages/markets";
import { MorePage, NotFoundPage, OnboardingPage } from "@/pages/misc";
import { RunPage, SearchPage } from "@/pages/search";

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
      { path: "avisos", element: <Page><NotificationsPage /></Page> },
      { path: "perfil", element: <Page><ProfilePage /></Page> },
      { path: "admin", element: <Page><AdminPage /></Page> },
      { path: "mais", element: <MorePage /> },
      { path: "ajuda", element: <HelpPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
