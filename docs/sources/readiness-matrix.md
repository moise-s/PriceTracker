# Matriz de prontidão das fontes

Última verificação: **27/09/2026**, execuções reais a partir da stack Docker local (PostgreSQL) e
dos smoke tests ao vivo (`make test-live`). Horários em America/Sao_Paulo (BRT, UTC−3).

Um adaptador só é considerado pronto quando encontra, com preço, produtos reais de naturezas
diferentes (embalagem, peso e unidade) numa filial identificada — abrir a página inicial não conta.

| Fonte | Domínio final | Filial testada | Método determinístico | Produtos de smoke test | Data/hora | Resultado | LLM | Limitações | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Angeloni** | `super.angeloni.com.br` | Beira Mar, Florianópolis (CEP 88025-202, seller `superangeloni14`) | API pública VTEX Intelligent Search com `region-id` obtido em `/api/checkout/pub/regions` (seller conferido) + ofertas "leve mais" do Master Data (`PR`) | Arroz branco 1 kg (embalagem), Alcatra kg (peso), Ovos 30 un (unidade) + cesta de 10 itens | 27/09 19:27–19:29 (smoke) e 19:19–19:21 (cesta) | Smoke 3/3 encontrados. Cesta: 9 encontrados, 1 **indisponível** (Café Três Corações Gourmet Sul de Minas, sem estoque) | Não usado | Preço online por filial (pode diferir da gôndola). Depende do mapeamento CEP → região VTEX; se o seller mudar, o alvo falha como `adapter_error` em vez de usar outra loja | **Pronto** |
| **Bistek** | `www.bistek.com.br` | Costeira do Pirajubaé, Florianópolis (preço de referência do site) | Sitemaps `/sitemap/product-{n}.xml` para descobrir URLs + página `/<slug>/p` com `__STATE__` embutido; revalidação por ETag. `robots.txt` proíbe `/busca` e `/api`, então a busca não é usada | Arroz 1 kg, Alcatra kg, Ovos 30 un + cesta de 10 itens | 27/09 19:27–19:29 (smoke) e 19:19–19:21 (cesta) | Smoke 3/3. Cesta: **10/10 encontrados** | Não usado | O site não permite escolher filial: todas as lojas Bistek recebem o mesmo preço online de referência (Florianópolis/SC). Isso é informado na UI. Descoberta depende dos sitemaps estarem atualizados | **Pronto** (com a ressalva de preço único) |
| **Fort Atacadista** | `fortatacadista.com.br` | Kobrasol, São José (loja `1638`) | Sitemap + `/produtos/<id>/<slug>` com a loja escolhida por cookie `st_334` (`userSelected=true`); lê `APOLLO_STATE` e **confere que a loja respondida é a pedida** | Arroz 1 kg, Alcatra kg, Ovos 30 un + cesta de 10 itens | 27/09 19:27–19:29 (smoke) e 19:19–19:21 (cesta) | Smoke 3/3. Cesta: 9 encontrados, 1 **não encontrado** (Maçã Fuji — não vendida online na loja) | Não usado | Preço online por loja; preços de atacado (por quantidade) são guardados e só usados quando a quantidade da lista atinge o mínimo. `robots.txt` bloqueia URLs com `?`, então nenhuma query string é usada | **Pronto** |
| **Imperatriz** | `clube.superimperatriz.com.br` (hotsite oficial do Super Clube) + API pública de ofertas (`api.zoombox.com.br`, `…execute-api.us-east-1.amazonaws.com`) | Mauro Ramos, Florianópolis (loja `9`) e Presidente Kennedy, São José (loja `16`) | JSON da API de ofertas do Super Clube; token público obtido no bootstrap do hotsite (mantido só em memória). Guarda preço de gôndola e preço de clube separados | Cesta de 10 itens; item em oferta: Leite condensado Tirol 395 g | 27/09 19:27–19:29 (smoke), 19:19–19:21 (cesta) e 19:33 (item em oferta) | API alcançável: **282 ofertas** vigentes na loja Mauro Ramos (2 requisições). Cesta: **10 não encontrados** (nenhum dos itens estava em oferta). Item em oferta: **encontrado**, gôndola R$ 5,79 e clube R$ 5,49 | Não usado | **Cobertura parcial por natureza da fonte**: só aparecem produtos em oferta do clube na semana. O catálogo completo está no iFood, protegido por anti-bot (PerimeterX) e termos de uso — **excluído** de propósito (não contornamos proteção). Preço de clube só entra se o usuário ativar o clube no perfil | **Degradado — requer decisão do usuário** |

## Evidência reproduzível

- **Cesta completa (4 mercados, 40 alvos):** run `8c3fe775`, status `success`, 28 encontrados,
  11 não encontrados, 1 indisponível, 100 s, 0 chamadas de LLM. Reproduzir:
  `make smoke CREDENTIALS=secrets/local-admin-credentials.txt` com a stack no ar.
- **Item em oferta no Imperatriz (4 mercados):** run `5365b85b` — Imperatriz encontrado (R$ 5,79;
  clube R$ 5,49), Bistek encontrado (R$ 6,49), Fort **indisponível** (R$ 5,39, promo R$ 4,98, sem
  estoque na loja), Angeloni **não encontrado**. Mostra os status distintos convivendo numa busca.
- **Smoke tests ao vivo:** `make test-live` → 4 passaram (27/09 22:27:38–22:29:17 UTC). Cobrem
  as três naturezas em Angeloni, Bistek e Fort e a disponibilidade das ofertas do Imperatriz.
- **Reinício no meio da coleta:** run `5f7acf67` interrompido com 19/40 alvos prontos por
  `docker compose down`; ao subir de novo foi retomado (tentativa 2, 21 pendentes) e terminou em
  `success`, com 29 observações e nenhuma duplicada.
- **Fixtures sanitizadas** das quatro fontes (capturadas em 27/09/2026) sustentam os testes de
  contrato determinísticos: `backend/tests/fixtures/`.

## Politeness aplicada a todas as fontes

`robots.txt` com casamento RFC 9309 (regra mais longa vence), allowlist de domínios validada também
em redirecionamentos, no máximo 2 conexões por host, intervalo mínimo entre requisições, timeout,
retries com backoff e jitter, circuit breaker por host, User-Agent identificável e nenhuma tentativa
de passar por CAPTCHA, login ou proteção anti-bot. Desafios (Cloudflare, Incapsula, PerimeterX)
viram status `blocked`, nunca dados inventados.

## Decisão pendente — Imperatriz

A execução real funciona, mas cobre só o que está em oferta no Super Clube. Opções:

1. **Manter como está (recomendado):** fonte oficial e legítima, cobertura parcial explícita na UI
   ("somente ofertas vigentes"); a comparação trata os itens ausentes como faltantes, sem vencedor
   injusto.
2. **Desativar o Imperatriz** na comparação semanal e usá-lo só para alertas de oferta.
3. **Buscar uma fonte adicional autorizada** (por exemplo, pedir ao Imperatriz acesso a um feed ou
   API de catálogo). iFood e outros agregadores protegidos por anti-bot continuam fora.

Enquanto não houver decisão, o critério "execução real comprovada nos quatro mercados" fica
**atendido para Angeloni, Bistek e Fort, e parcialmente para o Imperatriz**.
