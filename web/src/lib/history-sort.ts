import { getLocale, translate } from "./i18n";
import type { Schemas } from "@/api/client";

export type HistoryRow = Schemas["HistoryPointOut"] & { store: string };
export type HistorySortKey = "observed_at" | "store" | "title" | "price" | "unit_price" | "status";

/** Sort raw values, never formatted prices; missing values stay last in either direction. */
export function sortHistoryRows(rows: HistoryRow[], key: HistorySortKey, direction: "ascending" | "descending", locale = getLocale()): HistoryRow[] {
  const collator = new Intl.Collator(locale, { sensitivity: "base", numeric: true });
  const value = (row: HistoryRow): string | number | null => {
    if (key === "status") return translate(row.flagged ? "Em revisão" : row.stale ? "Desatualizado" : "Atual");
    if (key === "observed_at") return new Date(row.observed_at).getTime();
    if (key === "price" || key === "unit_price") {
      const amount = row[key] == null ? NaN : Number(row[key]);
      return Number.isFinite(amount) ? amount : null;
    }
    return row[key];
  };
  return [...rows].sort((a, b) => {
    const left = value(a), right = value(b);
    if (left === null || right === null) return left === right ? a.observation_id.localeCompare(b.observation_id) : left === null ? 1 : -1;
    const result = typeof left === "number" && typeof right === "number" ? left - right : collator.compare(String(left), String(right));
    return (direction === "ascending" ? result : -result) || a.observation_id.localeCompare(b.observation_id);
  });
}
