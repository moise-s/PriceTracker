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

## ADR-11 — Gestão regional com integrações explícitas

- **Contexto:** usuários de outras cidades precisavam editar o cadastro inicial e não tinham
  gestão de filiais pela interface. Endereço físico e região de preço online são conceitos distintos.
- **Decisão:** administradores gerenciam disponibilidade, apresentação e filiais das redes
  integradas; usuários filtram por região e mantêm sua própria seleção. Contextos são validados
  por adaptador (CEP/vendedor, ID oficial ou preço compartilhado); domínio, site e código de
  coleta das integrações iniciais continuam em código. Fontes novas passam pelo teste da ADR-12.
- **Persistência:** seed preserva campos administráveis das redes e filiais com origem `admin`.
  Desativação preserva histórico e filtra novas seleções/comparações; IDs explícitos indisponíveis
  são recusados, inclusive nas repetições e novos agendamentos. Buscas já criadas podem concluir.
- **Histórico:** depois de registrar uma busca, alterar a região de preço exige outro cadastro;
  não se reinterpretam observações antigas como preços de uma nova região.
- **Limites:** UI pt-BR/en, BRL e endereços brasileiros. Fontes fora do contrato público da ADR-12
  exigem adaptadores com fixtures e contexto verificável. Entrada manual/importação, outras moedas e
  formatos internacionais de endereço ficam no backlog.

## ADR-12 — Assistente de redes novas com fonte pública verificada

- **Contexto:** administrar filiais de quatro redes não permite usar a aplicação em regiões
  onde nenhuma delas existe. Cadastrar só um nome/site também não garante coleta utilizável.
- **Decisão:** administrador testa site HTTPS, produto público e sitemap; uma fonte com JSON-LD
  `Product` e uma `Offer` explícita em BRL pode ser cadastrada com a primeira loja na mesma
  transação. A fonte é testada novamente no cadastro; prévias enviadas pelo cliente não são prova.
  O índice pode ser revalidado/atualizado pela UI no mesmo domínio, para todas as lojas, sem
  mudar sua disponibilidade. Trocar o domínio exige outra rede para preservar a origem do histórico.
  As quatro integrações específicas mantêm seus contratos de região e promoções.
- **Cobertura:** referência online anônima, compartilhada entre filiais, com aviso e confirmação
  explícitos. Cidade/endereço não configuram região no site. Faixas de preço, múltiplas ofertas,
  condições por quantidade/cliente, validade expirada e outras moedas são recusadas.
- **Coleta:** sitemap de até 6 documentos/5.000 páginas, cache de 24 h e até 6 candidatos
  descobertos por produto. Cada anúncio ainda passa pelas regras de equivalência existentes.
  Sem JavaScript, login, configuração de CEP ou fallback de IA nesse adaptador.
- **Rede:** HTTPS, mesma origem configurada, robots e ritmo de acesso; cada conexão resolve
  todos os endereços DNS públicos e fixa o IP validado com Host/SNI originais. Endereços privados,
  credenciais e portas alternativas são recusados; documentos até 4 MB, teste até 35 s.
- **UX:** qualquer produto do catálogo pode virar cópia privada editável. Mercados mostra o
  resumo de produtos/lojas e uma ação que salva a seleção e cria a busca diretamente; opções
  avançadas e histórico continuam acessíveis separadamente.


## ADR-13 — Idioma local e comparação por metro — 02/10/2026

- **Contexto:** salvar um produto deixava dúvida sobre o estado do formulário; embalagens de
  papel higiênico com quantidades distintas precisavam de uma comparação equivalente.
- **Decisão:** salvar a criação retorna à lista, onde o usuário adiciona o produto. A UI permite
  pt-BR/en por navegador, sem traduzir nomes/dados do usuário ou termos de busca. README e guias
  de entrada, uso e fontes têm versões em inglês; moeda BRL e fuso da instalação permanecem.
- **Comprimento:** a unidade `m` representa metros totais. O modelo de folha dupla exige essa
  característica e permite tamanhos distintos; sem comprimento verificável, a oferta é recusada.
  A escolha usa preço por metro com quatro casas decimais. A cesta compra embalagens inteiras
  suficientes para os metros desejados e explica a sobra; alertas continuam por embalagem.
- **Fluxo:** o início mostra mercados selecionáveis. Atualizar preços salva a seleção e abre
  revisão da lista → confirmação dos mercados → início da busca. Histórico permite ordenar cada
  coluna nos dois sentidos, mantendo valores ausentes por último.
- **Persistência:** migração `0002` amplia as unidades permitidas; downgrade recusa dados em metros
  para evitar perda silenciosa. UI em inglês não amplia automaticamente a cobertura das fontes.
