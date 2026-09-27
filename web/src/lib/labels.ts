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
  pending: { label: "Na fila", tone: "neutral", icon: CircleDashed, help: "Aguardando a vez." },
  running: { label: "Buscando", tone: "info", icon: Loader2, help: "Consultando o mercado agora." },
  found: { label: "Encontrado", tone: "brand", icon: CheckCircle2, help: "Produto equivalente com preço." },
  not_found: { label: "Não encontrado", tone: "neutral", icon: SearchX, help: "A busca funcionou, mas nada equivalente apareceu." },
  unavailable: { label: "Indisponível", tone: "warn", icon: PackageX, help: "O produto existe, mas está sem estoque." },
  no_price: { label: "Sem preço", tone: "warn", icon: CircleSlash, help: "O produto existe, mas não mostra preço." },
  blocked: { label: "Bloqueado", tone: "danger", icon: ShieldAlert, help: "O site recusou o acesso automatizado (robots.txt, 403/429 ou proteção)." },
  timeout: { label: "Tempo esgotado", tone: "danger", icon: TimerOff, help: "O site demorou demais para responder." },
  adapter_error: { label: "Falha na fonte", tone: "danger", icon: Wrench, help: "Erro ao ler o site (mudança de layout ou indisponibilidade)." },
  needs_llm: { label: "Precisa de IA", tone: "warn", icon: Bot, help: "A leitura determinística falhou e não há IA configurada." },
  cancelled: { label: "Cancelado", tone: "neutral", icon: Ban, help: "Busca cancelada antes deste item." },
};

export const RUN_STATUS: Record<string, { label: string; tone: Tone; icon: LucideIcon }> = {
  queued: { label: "Na fila", tone: "neutral", icon: Clock3 },
  running: { label: "Em andamento", tone: "info", icon: Loader2 },
  success: { label: "Concluída", tone: "brand", icon: CheckCircle2 },
  partial: { label: "Concluída com falhas", tone: "warn", icon: AlertTriangle },
  failed: { label: "Falhou", tone: "danger", icon: XCircle },
  cancelled: { label: "Cancelada", tone: "neutral", icon: Ban },
};

export const CELL_STATUS: Record<string, { label: string; tone: Tone }> = {
  ok: { label: "Atual", tone: "brand" },
  stale: { label: "Desatualizado", tone: "warn" },
  flagged: { label: "Em revisão", tone: "danger" },
  unavailable: { label: "Indisponível", tone: "warn" },
  missing: { label: "Sem preço", tone: "neutral" },
  incompatible: { label: "Unidade incompatível", tone: "neutral" },
};

export const PRICE_KIND: Record<string, { label: string; tone: Tone }> = {
  regular: { label: "Preço normal", tone: "neutral" },
  promo: { label: "Promoção", tone: "accent" },
  club: { label: "Preço de clube", tone: "info" },
  quantity: { label: "Por quantidade", tone: "accent" },
};

export const CONFIDENCE: Record<string, { label: string; tone: Tone }> = {
  alta: { label: "Confiança alta", tone: "brand" },
  media: { label: "Confiança média", tone: "warn" },
  baixa: { label: "Confiança baixa", tone: "danger" },
};

export const HEALTH: Record<string, { label: string; tone: Tone }> = {
  saudavel: { label: "Funcionando", tone: "brand" },
  instavel: { label: "Instável", tone: "warn" },
  falhando: { label: "Com falhas", tone: "danger" },
  sem_dados: { label: "Sem dados ainda", tone: "neutral" },
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
};

export const SOLD_BY: Record<string, string> = {
  package: "Embalagem fechada",
  weight: "Por peso (kg)",
  unit: "Por unidade",
};

export const WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

export const REASON_TEXT: Record<string, string> = {
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
  if (REASON_TEXT[reason]) return REASON_TEXT[reason];
  const [key, value] = reason.split(":", 2);
  switch (key) {
    case "missing_required":
      return `não menciona “${value}”`;
    case "excluded":
      return `contém “${value}” (excluído)`;
    case "not_main_product":
      return `“${value}” não é o produto principal do título`;
    case "size_ok":
      return `tamanho confere (${value})`;
    case "size_within_tolerance":
      return `tamanho dentro da tolerância (${value})`;
    case "size_mismatch":
      return `tamanho diferente (${value})`;
    case "unit_mismatch":
      return `unidade diferente (${value})`;
    case "piece_too_large":
      return `peça grande demais (${value})`;
    case "multi_unit_pack":
      return `pacote com ${value} unidades`;
    case "unexpected_package":
      return `embalagem inesperada (${value})`;
    default:
      return reason;
  }
}
