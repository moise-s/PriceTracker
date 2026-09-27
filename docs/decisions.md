# Decisões e trade-offs

Registro curto no formato ADR (contexto → decisão → consequências). Datas: 27/09/2026.

## ADR-01 — Monólito modular com worker e fila no PostgreSQL

- **Contexto:** coletas levam minutos, precisam sobreviver a reinícios e não podem duplicar; a
  instalação é doméstica e deve ser leve.
- **Decisão:** FastAPI + serviços + domínio puro num pacote só; `worker` e `scheduler` como
  processos separados; fila nas tabelas `runs`/`run_targets` com claim
  `FOR UPDATE SKIP LOCKED`, heartbeat, recuperação de runs órfãos e devolução à fila no desligamento.
  Recorrências usam chave idempotente por ocorrência.
- **Consequências:** nenhum Redis/Celery; um único banco para fazer backup. O throughput é limitado
  (poucas coletas simultâneas), o que é adequado para uma casa. SQLite serializa escritas e serve
  só para desenvolvimento e testes.

## ADR-02 — Coleta determinística primeiro; LLM como fallback verificado

- **Contexto:** o protótipo dependia de LLM e de um modelo removido; LLM pode inventar preços.
- **Decisão:** cada adaptador usa primeiro dados estruturados públicos (API JSON, JSON-LD, estado
  embutido na página) e depois DOM determinístico. O LLM só recebe um trecho pequeno e sanitizado,
  tratado como dado não confiável, com schema JSON estrito; todo valor devolvido precisa aparecer no
  trecho (anti-fabricação) e as regras de matching são reaplicadas. Groq com `qwen/qwen3.8-27b` é o
  padrão (verificado com `pricetracker llm check`); OpenAI exige uma `OPENAI_API_KEY` da plataforma
  de API (a assinatura do ChatGPT não inclui créditos). Orçamento de chamadas por run e cache por hash.
- **Consequências:** nas execuções reais de 27/09 foram necessárias **0 chamadas** de LLM. Sem chave,
  só os alvos que precisariam de IA ficam `needs_llm`; o resto da busca segue normal.

## ADR-03 — Respeito às fontes em código, sem contornar proteções

- **Decisão:** cliente HTTP único com `robots.txt` (RFC 9309), allowlist de domínios inclusive em
  redirecionamentos, concorrência e intervalo por host, retries com backoff/jitter, circuit breaker,
  User-Agent identificável e detecção de desafios anti-bot, que viram `blocked`.
- **Consequências:** Bistek é lido por sitemaps (o `robots.txt` proíbe busca e API); Fort não usa
  query strings; o catálogo completo do Imperatriz no iFood fica de fora (ADR-07).

## ADR-04 — Dinheiro em Decimal/NUMERIC e quantidade da lista ≠ tamanho da embalagem

- **Decisão:** preços `NUMERIC(12,2)`, preço unitário `NUMERIC(14,4)`, quantidades `NUMERIC(12,3)`;
  a API trafega dinheiro como string decimal. A lista guarda "quanto comprar" (2 pacotes, 1,5 kg,
  12 unidades); a embalagem é característica da oferta. Itens vendidos a peso convertem embalagens
  aproximadas em preço por kg; preços por quantidade ("leve 3") só valem quando a quantidade atinge o
  mínimo; preço de clube só se o usuário ativar aquele clube.
- **Consequências:** nenhum float toca dinheiro; custos de linha são explicáveis ("2 × R$ 6,79").

## ADR-05 — Três visões de comparação e recomendação honesta

- **Decisão:** cesta comum (interseção), cobertura por mercado (sem vencedor injusto) e plano
  econômico que prioriza cobertura, inclui deslocamento, limita paradas e só divide a compra se
  economizar pelo menos R$ 5. Preços antigos (padrão 7 dias) exigem consentimento e baixam a
  confiança (baixa quando todos os preços usados são antigos); outliers ficam em revisão. Células
  vazias mostram o resultado da última busca.
- **Consequências:** a recomendação às vezes é "não há preços suficientes" — preferível a uma
  resposta errada.

## ADR-06 — Contas locais, sem e-mail

- **Decisão:** Argon2id, sessões opacas com hash no banco, cookies `HttpOnly`/`Secure`/`Lax`, CSRF
  double submit + Origin, rate limit por HMAC de usuário e cliente, 10 códigos de recuperação de uso
  único, reset pelo administrador com troca obrigatória. O primeiro administrador exige código de uma
  vez gerado no servidor (`pricetracker setup-code`); depois do bootstrap o autocadastro fica
  desligado (o admin pode ligar).
- **Consequências:** sem dependência de SMTP; perder senha e códigos exige um administrador.

## ADR-07 — Imperatriz: somente a fonte oficial do Super Clube

- **Contexto:** o site do Imperatriz não publica preços de catálogo; o catálogo completo está no
  iFood, protegido por anti-bot (PerimeterX) e termos de uso.
- **Decisão:** usar apenas a API pública de ofertas do hotsite oficial do Super Clube, guardando
  preço de gôndola e preço de clube separados, e declarar a cobertura parcial na UI.
- **Consequências:** itens fora de oferta aparecem como "não encontrado" no Imperatriz. **Requer
  decisão do usuário** (opções em `docs/sources/readiness-matrix.md`).

## ADR-08 — Geografia sem serviços públicos recorrentes

- **Decisão:** endereço com coordenadas informadas pelo usuário (ou geolocalização do navegador);
  Nominatim só como opção explícita, com contato configurado e cache (nunca para autocomplete);
  distância por OSRM auto-hospedado opcional ou estimativa `haversine × 1,35`, sempre com a fórmula
  visível.
- **Consequências:** zero dependência externa por padrão; a estimativa pode errar em trajetos com
  pontes/serras — por isso o método aparece na UI ("Distância estimada") e o OSRM é recomendado para
  quem quiser precisão.

## ADR-09 — Implantação somente local

- **Contexto:** o dono do projeto pediu explicitamente para não tratar de deploy em servidor.
- **Decisão:** Docker Compose local, publicado só em `127.0.0.1:8090`, com segredos em arquivos,
  backups e restauração testados. Tailscale Serve, systemd e servidor ficam fora do escopo.
- **Consequências:** para uso em outro dispositivo da casa será preciso um passo adicional
  (proxy HTTPS/Tailscale), deixado no backlog.

## ADR-10 — Testes de ponta a ponta com backend determinístico

- **Decisão:** um harness de testes (`backend/tests/e2e_harness.py`) sobe a API real com SQLite
  descartável e um worker em processo que replica as fixtures sanitizadas; uma API de controle
  (montada só no harness) reseta o estado e injeta falhas por mercado. O Playwright roda contra o
  build de produção (`vite preview`).
- **Consequências:** os oito cenários rodam em ~1 min, sem rede externa e sem flakiness de sites
  reais; a validação contra os sites reais fica nos smoke tests ao vivo e nas execuções da stack.
