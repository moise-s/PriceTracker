import "./styles.css";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { toast, Toaster } from "sonner";
import { useRegisterSW } from "virtual:pwa-register/react";
import { ApiError } from "@/api/client";
import { router } from "@/app/router";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
  mutationCache: new MutationCache({
    onError: (error) => {
      if (error instanceof ApiError && error.status === 401) window.location.assign("/entrar");
    },
  }),
});

function UpdatePrompt() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW();
  useEffect(() => {
    if (needRefresh) {
      toast("Nova versão disponível", { action: { label: "Atualizar", onClick: () => void updateServiceWorker(true) }, duration: Infinity });
    }
  }, [needRefresh, updateServiceWorker]);
  return null;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster position="top-center" richColors closeButton toastOptions={{ className: "font-sans" }} />
      {import.meta.env.PROD ? <UpdatePrompt /> : null}
    </QueryClientProvider>
  </StrictMode>,
);
