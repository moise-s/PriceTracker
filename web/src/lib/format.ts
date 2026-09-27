const TZ = "America/Sao_Paulo";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const brlCompact = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const oneDecimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

type Numeric = string | number | null | undefined;

function toNumber(value: Numeric): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Display-only formatting; money arrives from the API as decimal strings. */
export function money(value: Numeric, fallback = "—"): string {
  const n = toNumber(value);
  return n === null ? fallback : brl.format(n);
}

export function moneyCompact(value: Numeric): string {
  const n = toNumber(value);
  return n === null ? "—" : brlCompact.format(n);
}

export function number(value: Numeric, fallback = "—"): string {
  const n = toNumber(value);
  return n === null ? fallback : decimal.format(n);
}

export function km(value: Numeric): string {
  const n = toNumber(value);
  return n === null ? "—" : `${oneDecimal.format(n)} km`;
}

const UNIT_LABEL: Record<string, string> = { kg: "kg", g: "g", l: "L", ml: "ml", un: "un", pct: "pct" };

export function unitPrice(value: Numeric, unit: string | null | undefined): string {
  const n = toNumber(value);
  if (n === null || !unit) return "—";
  return `${brl.format(n)}/${UNIT_LABEL[unit] ?? unit}`;
}

export function quantity(value: Numeric, unit: string): string {
  const n = toNumber(value);
  if (n === null) return "—";
  if (unit === "pct") return `${decimal.format(n)} ${n === 1 ? "pacote" : "pacotes"}`;
  if (unit === "un") return `${decimal.format(n)} ${n === 1 ? "unidade" : "unidades"}`;
  if (unit === "kg" && n < 1) return `${decimal.format(n * 1000)} g`;
  return `${decimal.format(n)} ${UNIT_LABEL[unit] ?? unit}`;
}

export function packageLabel(quantityValue: Numeric, unit: string | null | undefined, soldBy: string): string {
  if (soldBy === "weight") return "por kg";
  if (soldBy === "unit") return "por unidade";
  const n = toNumber(quantityValue);
  if (n === null || !unit) return "embalagem";
  if (unit === "un") return `${decimal.format(n)} un`;
  return `${decimal.format(n)} ${UNIT_LABEL[unit] ?? unit}`;
}

const dateTime = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const dateOnly = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "short", year: "numeric" });
const shortDate = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit" });
const relative = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateOnly.format(new Date(iso)) : "—";
}

export function formatShortDate(iso: string | number | Date): string {
  return shortDate.format(new Date(iso));
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(seconds);
  if (abs < 60) return "agora";
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), "hour");
  return relative.format(Math.round(seconds / 86400), "day");
}

export function ageDays(iso: string | null | undefined): number | null {
  if (!iso) return null;
  return (Date.now() - new Date(iso).getTime()) / 86_400_000;
}

export function pluralize(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** Parses a money amount typed in pt-BR ("7,50", "1.234,50") or with a dot ("7.50"). */
export function parseMoneyInput(text: string): number | null {
  const cleaned = text.replace(/R\$|\s/g, "");
  if (!cleaned) return null;
  const normalized = cleaned.includes(",") ? cleaned.replace(/\./g, "").replace(",", ".") : cleaned;
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  const value = Number(normalized);
  return value > 0 ? value : null;
}
