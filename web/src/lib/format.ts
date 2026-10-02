import { getLocale, translate } from "./i18n";
const TZ = "America/Sao_Paulo";

const formats = Object.fromEntries((["pt-BR", "en"] as const).map((locale) => [locale, {
  brl: new Intl.NumberFormat(locale, { style: "currency", currency: "BRL" }),
  brlCompact: new Intl.NumberFormat(locale, { style: "currency", currency: "BRL", maximumFractionDigits: 0 }),
  decimal: new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }),
  oneDecimal: new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  dateTime: new Intl.DateTimeFormat(locale, { timeZone: TZ, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }),
  dateOnly: new Intl.DateTimeFormat(locale, { timeZone: TZ, day: "2-digit", month: "short", year: "numeric" }),
  shortDate: new Intl.DateTimeFormat(locale, { timeZone: TZ, day: "2-digit", month: "2-digit" }),
  relative: new Intl.RelativeTimeFormat(locale, { numeric: "auto" }),
}]));
const currentFormats = () => formats[getLocale()]!;

type Numeric = string | number | null | undefined;

function toNumber(value: Numeric): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Display-only formatting; money arrives from the API as decimal strings. */
export function money(value: Numeric, fallback = "—"): string {
  const n = toNumber(value);
  return n === null ? fallback : currentFormats().brl.format(n);
}

export function moneyCompact(value: Numeric): string {
  const n = toNumber(value);
  return n === null ? "—" : currentFormats().brlCompact.format(n);
}

export function number(value: Numeric, fallback = "—"): string {
  const n = toNumber(value);
  return n === null ? fallback : currentFormats().decimal.format(n);
}

export function km(value: Numeric): string {
  const n = toNumber(value);
  return n === null ? "—" : `${currentFormats().oneDecimal.format(n)} km`;
}

const UNIT_LABEL: Record<string, string> = { kg: "kg", g: "g", l: "L", ml: "ml", m: "m", un: "un", pct: "pct" };

export function unitPrice(value: Numeric, unit: string | null | undefined): string {
  const n = toNumber(value);
  if (n === null || !unit) return "—";
  return `${(unit === "m" ? new Intl.NumberFormat(getLocale(), { style: "currency", currency: "BRL", minimumFractionDigits: 4, maximumFractionDigits: 4 }) : currentFormats().brl).format(n)}/${UNIT_LABEL[unit] ?? unit}`;
}

export function quantity(value: Numeric, unit: string): string {
  const n = toNumber(value);
  if (n === null) return "—";
  if (unit === "pct") return `${currentFormats().decimal.format(n)} ${translate(n === 1 ? "pacote" : "pacotes")}`;
  if (unit === "un") return `${currentFormats().decimal.format(n)} ${translate(n === 1 ? "unidade" : "unidades")}`;
  if (unit === "kg" && n < 1) return `${currentFormats().decimal.format(n * 1000)} g`;
  return `${currentFormats().decimal.format(n)} ${UNIT_LABEL[unit] ?? unit}`;
}

export function packageLabel(quantityValue: Numeric, unit: string | null | undefined, soldBy: string): string {
  if (soldBy === "weight") return translate("por kg");
  if (soldBy === "unit") return translate("por unidade");
  const n = toNumber(quantityValue);
  if (n === null || !unit) return translate("embalagem");
  if (unit === "un") return `${currentFormats().decimal.format(n)} un`;
  return `${currentFormats().decimal.format(n)} ${UNIT_LABEL[unit] ?? unit}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? currentFormats().dateTime.format(new Date(iso)) : "—";
}

export function formatDate(iso: string | null | undefined): string {
  return iso ? currentFormats().dateOnly.format(new Date(iso)) : "—";
}

export function formatShortDate(iso: string | number | Date): string {
  return currentFormats().shortDate.format(new Date(iso));
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return translate("nunca");
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(seconds);
  if (abs < 60) return translate("agora");
  if (abs < 3600) return currentFormats().relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return currentFormats().relative.format(Math.round(seconds / 3600), "hour");
  return currentFormats().relative.format(Math.round(seconds / 86400), "day");
}

export function ageDays(iso: string | null | undefined): number | null {
  if (!iso) return null;
  return (Date.now() - new Date(iso).getTime()) / 86_400_000;
}

export function pluralize(count: number, singular: string, plural: string): string {
  return `${count} ${translate(count === 1 ? singular : plural)}`;
}

/** Parses a money amount typed in pt-BR ("7,50", "1.234,50") or with a dot ("7.50"). */
export function parseMoneyInput(text: string): number | null {
  const cleaned = text.replace(/R\$|\s/g, "");
  if (!cleaned) return null;
  const normalized = cleaned.includes(",") && cleaned.includes(".")
    ? cleaned.lastIndexOf(",") > cleaned.lastIndexOf(".") ? cleaned.replace(/\./g, "").replace(",", ".") : cleaned.replace(/,/g, "")
    : cleaned.replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  const value = Number(normalized);
  return value > 0 ? value : null;
}
