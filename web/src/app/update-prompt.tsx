import { translate, useLocale } from "@/lib/i18n";
import { useEffect } from "react";
import { toast } from "sonner";
import { useRegisterSW } from "virtual:pwa-register/react";

/** Offers a reload when a new service worker (new app version) is waiting. */
export function UpdatePrompt() {
  const locale = useLocale();
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW();
  useEffect(() => {
    if (needRefresh) {
      toast(translate("Nova versão disponível"), { action: { label: translate("Atualizar"), onClick: () => void updateServiceWorker(true) }, duration: Infinity });
    }
  }, [needRefresh, updateServiceWorker, locale]);
  return null;
}
