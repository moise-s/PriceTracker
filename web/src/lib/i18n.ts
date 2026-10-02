import { useSyncExternalStore } from "react";
import { EN } from "./translations";

export type Locale = "pt-BR" | "en";
const STORAGE_KEY = "pricetracker.language";
const listeners = new Set<() => void>();
function initialLocale(): Locale {
  try { return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "pt-BR"; } catch { return "pt-BR"; }
}
let locale: Locale = initialLocale();
export function getLocale(): Locale { return locale; }
export function setLocale(next: Locale): void {
  locale = next;
  try { localStorage.setItem(STORAGE_KEY, next); } catch { /* Storage can be unavailable in private browsing. */ }
  document.documentElement.lang = next;
  for (const listener of listeners) listener();
}
function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function useLocale(): Locale { return useSyncExternalStore(subscribe, getLocale, () => "pt-BR"); }
if (typeof document !== "undefined") document.documentElement.lang = locale;

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const templates = Object.entries(EN).filter(([key]) => /\{\d+\}/.test(key)).map(([key, english]) => {
  const parts = key.split(/(\{\d+\})/);
  const slots = parts.filter((part) => /^\{\d+\}$/.test(part));
  return { pattern: new RegExp(`^${parts.map((part) => /^\{\d+\}$/.test(part) ? "(.*?)" : escape(part)).join("")}$`, "s"), slots, english };
});

/** Translate UI messages only. Elements, numbers and source data pass through. */
export function translate<T>(value: T): T {
  if (locale !== "en" || typeof value !== "string") return value;
  const key = value.trim();
  let english = EN[key];
  if (english === undefined) {
    for (const template of templates) {
      const match = template.pattern.exec(key);
      if (match) {
        const substitutions = Object.fromEntries(template.slots.map((slot, index) => [slot, match[index + 1]! ]));
        english = template.english.replace(/\{\d+\}/g, (slot) => substitutions[slot] ?? slot);
        break;
      }
    }
  }
  return (english === undefined ? value : value.replace(key, () => english!)) as T;
}
