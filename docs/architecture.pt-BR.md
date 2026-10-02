# Arquitetura do PriceTracker v1

[English](architecture.md)

O PriceTracker responde a uma pergunta de casa: **onde a compra da semana sai mais barata quando o
deslocamento entra na conta** — com cobertura, frescor e confiança explícitos. A v1 é uma
reconstrução completa; o protótipo v0 está arquivado em `legacy/v0/` e o banco SQLite antigo não é
importado nem suportado.

## Forma: monólito modular com worker dedicado

```
Navegador (PWA pt-BR/en: React + TypeScript + Vite)
   │  http://localhost:8090 (somente loopback)
   ▼
web  (Caddy: SPA estática + proxy /api → api, CSP e cabeçalhos de segurança)
   │
   ▼
api  (FastAPI, Pydantic, SQLAlchemy) ───┐
worker (coletas assíncronas) ───────────┼──► db (PostgreSQL 17: dados + fila durável)
scheduler (recorrências → fila) ────────┘     volume app_data (imagens enviadas)
   │
   └─► adaptadores de mercado ──► sites dos supermercados (robots, allowlist, ritmo educado)
       └─► provedor de LLM (fallback opcional; schema JSON estrito; nunca obrigatório)
```

| Camada | Pacote | Responsabilidade |
| --- | --- | --- |
| API | `pricetracker.api` | REST versionada (`/api/v1`), OpenAPI, autenticação/CSRF, autorização por usuário |
| Serviços | `pricetracker.services` | Casos de uso: contas, catálogo, listas, buscas, comparação, histórico, alertas, admin |
| Domínio | `pricetracker.domain` | Lógica pura: dinheiro, unidades, matching, cesta, deslocamento, frescor, outliers |
| Adaptadores | `pricetracker.adapters` | Um adaptador por mercado atrás de um contrato comum; cliente HTTP educado |
| LLM | `pricetracker.llm` | Provedores intercambiáveis (Groq, OpenAI, compatível com OpenAI) só como fallback |
| Geo | `pricetracker.geo` | Geocodificação/rotas intercambiáveis (manual, Nominatim opcional, OSRM opcional, estimativa) + cache |
| Jobs | `pricetracker.worker`, `pricetracker.scheduler` | Fila no PostgreSQL com claim transacional (`FOR UPDATE SKIP LOCKED`) |
| Persistência | `pricetracker.db`, `pricetracker.models`, `migrations/` | Modelos SQLAlchemy 2 e migrations Alembic (schema novo) |
| Web | `web/` | SPA React consumindo cliente tipado gerado do OpenAPI |

## Fluxo de uma busca

1. O usuário pede uma busca (ou o scheduler enfileira uma recorrência com chave idempotente
   `schedule:<id>:<ocorrência>`). A API cria o `run` e um alvo por produto × loja.
2. O worker faz o claim do run (`UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED)`), mantém
   heartbeat e processa os alvos com concorrência limitada. Alvos com o mesmo contexto de preço
   (ex.: todas as lojas Bistek, que têm preço único) compartilham uma única consulta.
3. Para cada alvo: adaptador → listagens determinísticas → `MatchSpec` (termos, grupos obrigatórios,
   exclusões, marca, tamanho com tolerância, "produto principal nas 3 primeiras palavras") →
   melhor preço unitário comparável. Se a leitura determinística falhar e houver trecho
   sanitizado, o LLM pode extrair itens — e cada valor devolvido precisa existir no trecho.
4. O alvo termina em exatamente um status: `found`, `not_found`, `unavailable`, `no_price`,
   `blocked`, `timeout`, `adapter_error`, `needs_llm` ou `cancelled`. O run é `success` sem falhas,
   `partial` com falhas, `failed` sem nenhum resultado legítimo, `cancelled` a pedido.
5. Observações guardam método (`api`, `json_ld`, `embedded_state`, `dom`, `llm`), confiança,
   versão do adaptador, URL, filial, horário, payload bruto sanitizado e avaliação de outlier.
6. Ao terminar, os alertas de preço do usuário são avaliados contra as observações desse run.
7. Se o worker for desligado, o run volta para a fila sem perder alvos concluídos; se o worker
   morrer, o scheduler/worker recupera runs sem heartbeat.

## Comparação

Três visões sobre as observações mais recentes de cada produto × loja:

- **Cesta comum:** só os itens encontrados em todas as lojas; vencedor pelo menor total.
- **Por mercado (cobertura):** total de cada loja com "X de Y itens"; lojas incompletas são
  marcadas "total não comparável" e nunca vencem só por estarem incompletas.
- **Plano econômico:** prioriza cobertura, depois custo efetivo (produtos + deslocamento), com até
  N paradas (padrão 2, máx. 3) e rota exata casa → lojas → casa. Divisão só se economizar ≥ R$ 5.

Deslocamento = `distância ÷ km/l × R$/l + pedágios`, mostrado com a fórmula e os valores. A
distância vem de OSRM auto-hospedado (opcional) ou de estimativa `haversine × 1,35`. Preços com mais
de N dias (padrão 7) ficam no histórico mas não entram na recomendação sem consentimento explícito;
outliers ficam sinalizados para revisão e não são usados. Cada célula vazia diz o motivo (resultado
da última busca: não encontrado, bloqueado, tempo esgotado…). A confiança (alta/média/baixa)
considera cobertura, preços antigos autorizados, uso de IA, pesos estimados e deslocamento.

## Segurança e privacidade

- Contas locais: Argon2id, sessões opacas guardadas como hash em cookie `HttpOnly`, `Secure`,
  `SameSite=Lax`; CSRF por double submit + checagem de `Origin`; rate limit de login; códigos de
  recuperação no lugar de e-mail; primeiro administrador exige código de configuração gerado no
  servidor.
- Multiusuário por construção: toda linha do usuário tem `user_id` e todo serviço filtra por ele.
  Catálogo global, mercados e lojas são curados por administradores.
- Segredos de ambiente vêm de arquivos (`./secrets`, Docker secrets ou `*_FILE`), sem passar
  pelo frontend, logs ou Git. Chaves configuradas pela administração são armazenadas criptografadas
  no banco. Logs estruturados em JSON ocultam chaves, tokens, cookies e senhas.
- Imagens enviadas são revalidadas e recodificadas em WebP; SVG é recusado; importação por URL
  resolve DNS e só aceita IP público (proteção contra SSRF), revalidando cada redirecionamento.

## Implantação

Somente local, por decisão do dono do projeto: Docker Compose com `db`, `migrate` (one-shot),
`api`, `worker`, `scheduler` e `web`, imagens com versão fixada (digest no PostgreSQL), usuário não
root, sistema de arquivos somente leitura, `no-new-privileges`, health checks, limites de CPU/memória
e volumes nomeados. Só `127.0.0.1:8090` é publicado. Implantação em servidor (e Tailscale Serve) está
fora do escopo desta entrega; ver `docs/operations.md`.

## Qualidade

- Backend: testes unitários, de contrato (fixtures sanitizadas das quatro fontes) e de integração;
  a suíte roda em SQLite e, opcionalmente, em PostgreSQL (`make test-pg`) com testes de fila
  concorrente. Smoke tests ao vivo são opt-in (`make test-live`).
- Web: testes unitários (Vitest) e E2E (Playwright) contra um backend determinístico
  (`backend/tests/e2e_harness.py`) que replica as fixtures sem sair da máquina.
- Detalhes e resultados em `docs/testing.md`; decisões em `docs/decisions.md`.
