import { translate } from "./i18n";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Ban,
  Bot,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Clock3,
  Loader2,
  PackageX,
  SearchX,
  ShieldAlert,
  TimerOff,
  Wrench,
  XCircle,
} from "lucide-react";

export type Tone = "neutral" | "brand" | "accent" | "warn" | "danger" | "info";

export const TARGET_STATUS: Record<string, { label: string; tone: Tone; icon: LucideIcon; help: string }> = {
  pending: { get label() { return translate("Na fila"); }, tone: "neutral", icon: CircleDashed, get help() { return translate("Aguardando a vez."); } },
  running: { get label() { return translate("Buscando"); }, tone: "info", icon: Loader2, get help() { return translate("Consultando o mercado agora."); } },
  found: { get label() { return translate("Encontrado"); }, tone: "brand", icon: CheckCircle2, get help() { return translate("Produto equivalente com preço."); } },
  not_found: { get label() { return translate("Não encontrado"); }, tone: "neutral", icon: SearchX, get help() { return translate("A busca funcionou, mas nada equivalente apareceu."); } },
  unavailable: { get label() { return translate("Indisponível"); }, tone: "warn", icon: PackageX, get help() { return translate("O produto existe, mas está sem estoque."); } },
  no_price: { get label() { return translate("Sem preço"); }, tone: "warn", icon: CircleSlash, get help() { return translate("O produto existe, mas não mostra preço."); } },
  blocked: { get label() { return translate("Bloqueado"); }, tone: "danger", icon: ShieldAlert, get help() { return translate("O site recusou o acesso automatizado (robots.txt, 403/429 ou proteção)."); } },
  timeout: { get label() { return translate("Tempo esgotado"); }, tone: "danger", icon: TimerOff, get help() { return translate("O site demorou demais para responder."); } },
  adapter_error: { get label() { return translate("Falha na fonte"); }, tone: "danger", icon: Wrench, get help() { return translate("Erro ao ler o site (mudança de layout ou indisponibilidade)."); } },
  needs_llm: { get label() { return translate("Precisa de IA"); }, tone: "warn", icon: Bot, get help() { return translate("A leitura determinística falhou e não há IA configurada."); } },
  cancelled: { get label() { return translate("Cancelado"); }, tone: "neutral", icon: Ban, get help() { return translate("Busca cancelada antes deste item."); } },
};

export const RUN_STATUS: Record<string, { label: string; tone: Tone; icon: LucideIcon }> = {
  queued: { get label() { return translate("Na fila"); }, tone: "neutral", icon: Clock3 },
  running: { get label() { return translate("Em andamento"); }, tone: "info", icon: Loader2 },
  success: { get label() { return translate("Concluída"); }, tone: "brand", icon: CheckCircle2 },
  partial: { get label() { return translate("Concluída com falhas"); }, tone: "warn", icon: AlertTriangle },
  failed: { get label() { return translate("Falhou"); }, tone: "danger", icon: XCircle },
  cancelled: { get label() { return translate("Cancelada"); }, tone: "neutral", icon: Ban },
};

export const CELL_STATUS: Record<string, { label: string; tone: Tone }> = {
  ok: { get label() { return translate("Atual"); }, tone: "brand" },
  stale: { get label() { return translate("Desatualizado"); }, tone: "warn" },
  flagged: { get label() { return translate("Em revisão"); }, tone: "danger" },
  unavailable: { get label() { return translate("Indisponível"); }, tone: "warn" },
  missing: { get label() { return translate("Sem preço"); }, tone: "neutral" },
  incompatible: { get label() { return translate("Unidade incompatível"); }, tone: "neutral" },
};

export const PRICE_KIND: Record<string, { label: string; tone: Tone }> = {
  regular: { get label() { return translate("Preço normal"); }, tone: "neutral" },
  promo: { get label() { return translate("Promoção"); }, tone: "accent" },
  club: { get label() { return translate("Preço de clube"); }, tone: "info" },
  quantity: { get label() { return translate("Por quantidade"); }, tone: "accent" },
};

export const CONFIDENCE: Record<string, { label: string; tone: Tone }> = {
  alta: { get label() { return translate("Confiança alta"); }, tone: "brand" },
  media: { get label() { return translate("Confiança média"); }, tone: "warn" },
  baixa: { get label() { return translate("Confiança baixa"); }, tone: "danger" },
};

export const HEALTH: Record<string, { label: string; tone: Tone }> = {
  saudavel: { get label() { return translate("Funcionando"); }, tone: "brand" },
  instavel: { get label() { return translate("Instável"); }, tone: "warn" },
  falhando: { get label() { return translate("Com falhas"); }, tone: "danger" },
  sem_dados: { get label() { return translate("Sem dados ainda"); }, tone: "neutral" },
};

export const METHOD: Record<string, string> = {
  api: "API pública do site",
  json_ld: "Dados estruturados (JSON-LD)",
  embedded_state: "Dados da página do produto",
  dom: "Leitura da página",
  llm: "Extraído com ajuda de IA",
};

export const UNIT_OPTIONS: Record<string, string> = {
  pct: "pacote(s)",
  un: "unidade(s)",
  kg: "kg",
  g: "g",
  l: "L",
  ml: "ml",
  m: "m (metros)",
};

export const SOLD_BY: Record<string, string> = {
  package: "Embalagem fechada",
  weight: "Por peso (kg)",
  unit: "Por unidade",
};

export const WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

export const REASON_TEXT: Record<string, string> = {
  compared_per_metre: "comparado pelo preço por metro, aceitando tamanhos diferentes",
  length_unknown: "comprimento total da embalagem não identificado",
  pin_rejected: "você marcou como produto errado",
  pin_accepted: "confirmado por você",
  gtin_match: "mesmo código de barras",
  brand_preferred: "marca preferida",
  brand_mismatch: "marca diferente da exigida",
  sold_per_kg: "vendido por kg",
  variable_weight_piece: "peça de peso variável",
  variable_weight_pack: "bandeja de peso aproximado",
  fixed_weight_pack: "embalagem com peso fixo",
  not_sold_by_weight: "não é vendido por peso",
  sold_per_unit: "vendido por unidade",
  per_kg_with_estimated_unit_weight: "vendido por kg (peso médio estimado)",
  sold_per_kg_without_unit_weight: "vendido por kg sem peso médio",
  assumed_single_unit: "vendido por unidade (presumido)",
  no_size_rule: "sem regra de tamanho",
  sold_per_kg_not_package: "vendido a granel, não em pacote",
  count_unknown: "quantidade de unidades não identificada",
  size_unknown: "tamanho não identificado",
  bulk_per_kg_allowed: "granel permitido",
};

export function explainReason(reason: string): string {
  if (REASON_TEXT[reason]) return translate(REASON_TEXT[reason]);
  const [key, value] = reason.split(":", 2);
  switch (key) {
    case "missing_required":
      return translate(`não menciona “${value}”`);
    case "excluded":
      return translate(`contém “${value}” (excluído)`);
    case "not_main_product":
      return translate(`“${value}” não é o produto principal do título`);
    case "size_ok":
      return translate(`tamanho confere (${value})`);
    case "size_within_tolerance":
      return translate(`tamanho dentro da tolerância (${value})`);
    case "size_mismatch":
      return translate(`tamanho diferente (${value})`);
    case "unit_mismatch":
      return translate(`unidade diferente (${value})`);
    case "piece_too_large":
      return translate(`peça grande demais (${value})`);
    case "multi_unit_pack":
      return translate(`pacote com ${value} unidades`);
    case "unexpected_package":
      return translate(`embalagem inesperada (${value})`);
    default:
      return reason;
  }
}
