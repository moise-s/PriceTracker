import { useEffect } from "react";
import { toast } from "sonner";
import { useRegisterSW } from "virtual:pwa-register/react";

/** Offers a reload when a new service worker (new app version) is waiting. */
export function UpdatePrompt() {
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
