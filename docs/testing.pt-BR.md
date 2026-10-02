# Testes e evidências

[English](testing.md)

## Como rodar

| Comando | O que roda |
| --- | --- |
| `make test` | Backend (pytest, SQLite) + testes unitários da web (Vitest) |
| `make test-pg` | Suíte do backend em PostgreSQL (precisa de `make dev-db`), incluindo testes de fila concorrente |
| `make test-live` | Smoke tests contra os sites reais (opt-in, educados, poucos produtos) |
| `make e2e` | Playwright: sobe o harness determinístico + build de produção e roda os cenários |
| `make lint` / `make typecheck` | ruff + oxlint / mypy strict + tsc |
| `make secrets-scan` | gitleaks no histórico do Git |
| `make smoke CREDENTIALS=…` | Coleta real completa na stack Docker em execução (`scripts/stack_smoke.py`) |

O E2E usa o Google Chrome instalado (sem baixar navegador). Para usar o Chromium do Playwright:
`npx playwright install chromium` e `PLAYWRIGHT_CHANNEL=bundled make e2e`.

## Resultados (27/09/2026)

| Suíte | Resultado |
| --- | --- |
| Backend em SQLite | **133 passaram**, 6 pulados (4 ao vivo, 2 exclusivos de PostgreSQL) |
| Backend em PostgreSQL 17.10 | **135 passaram**, 4 pulados (ao vivo) |
| Smoke ao vivo (`--live`) | **4 passaram** (22:27–22:29 UTC): Angeloni, Bistek e Fort com embalagem/peso/unidade; ofertas do Imperatriz |
| Web unitários (Vitest) | **26 passaram** |
| E2E (Playwright) | **17 passaram**: 8 cenários × desktop (1280×900) e mobile (390×844) + matriz de telas |
| Lint e tipos | ruff, mypy strict, oxlint e tsc sem avisos |
| Provedor de IA | `pricetracker llm check` na stack: Groq `qwen/qwen3.8-27b`, conexão ok (259 ms) |
| Segredos | gitleaks: nenhum vazamento no histórico |

## Cenários E2E

Todos rodam contra `backend/tests/e2e_harness.py` (API real, SQLite descartável, worker em processo
com as fixtures sanitizadas; nada sai da máquina). Screenshots de cada passo ficam no relatório HTML
do Playwright (`web/playwright-report/`).

| # | Cenário | O que é verificado |
| --- | --- | --- |
| 1 | Compra da semana | Primeiro acesso com código de configuração → códigos de recuperação → boas-vindas → lista montada pelo catálogo → lojas marcadas na tela de mercados → busca → "Concluída" → recomendação com cobertura 4/4 e aviso de deslocamento não configurado |
| 2 | Item ausente | Maçã Fuji não existe no Fort: o Angeloni completo vence, a célula vazia diz "Não encontrado", a cesta comum exclui o item e o Fort aparece como "Total não comparável" (2 de 3) |
| 3 | Deslocamento muda o vencedor | Sem deslocamento o Fort ganha (R$ 26,46 × R$ 29,77); com a casa perto do Angeloni Beira Mar e o Fort a ~12 km, o Angeloni ganha; a fórmula "km ÷ 10 km/l × R$ 6,29/l" aparece |
| 4 | IA indisponível | O Bistek "muda de layout" e não há chave de IA: só os alvos dele ficam "Precisa de IA"; o Fort segue válido e a comparação funciona |
| 5 | Falha parcial | O Angeloni responde com desafio anti-bot: busca "Concluída com falhas", status "Bloqueado", botão "Repetir falhas (2)"; após o site voltar, a repetição conclui e a comparação fica completa sem perder o que já havia |
| 6 | Isolamento | Um segundo usuário não vê o produto, a lista, a busca nem o endereço do primeiro (UI e API devolvem 404/vazio) |
| 7 | Frescor | Preços com 10 dias ficam "Desatualizado" e fora da recomendação; ao autorizar, a recomendação volta com "Confiança baixa" e aviso explícito |
| 8 | Alerta de preço | Alvo criado na página do produto → busca → aviso "R$ 6,79 por embalagem" em Avisos, selo "No alvo" e contador no sino; marcar como lido zera o contador |

## Matriz de telas

`web/e2e/screens.spec.ts` abre 10 telas (início, lista, mercados, busca, onde compensa, histórico,
produto, avisos, perfil, administração) em **360, 390, 1280 e 1440 px** e mais três telas em modo
escuro (390 e 1280). O teste falha se houver rolagem horizontal, conteúdo cortado na borda da tela
ou violação *serious/critical* do axe (WCAG 2.1 A/AA). As imagens ficam em `docs/screenshots/`:

- `docs/screenshots/<largura>/<tela>.jpg` (ex.: `390/onde-compensa.jpg`, `1280/inicio.jpg`)
- `docs/screenshots/dark/<tela>-<largura>.jpg`

## Execuções reais na stack Docker

| Evidência | Resultado |
| --- | --- |
| Coleta completa (10 itens × 4 mercados) | `success`, 28 encontrados, 11 não encontrados, 1 indisponível, 100 s, 0 chamadas de IA |
| Item em oferta no Imperatriz | encontrado no Imperatriz (R$ 5,79) e no Bistek (R$ 6,49), indisponível no Fort, não encontrado no Angeloni |
| Reinício no meio da coleta | retomada do ponto em que parou, sem observações duplicadas |
| Backup e restauração | drill PASS; restauração real conferida |

Detalhes por fonte em `docs/sources/readiness-matrix.md`.
## Verificação da gestão regional — 02/10/2026

Na branch `feat/rebuild-v1`, a suíte determinística do backend passou com **146 testes**, com
**6 ignorados** (2 dependem de PostgreSQL e 4 fazem acesso ao vivo). Vitest: **26 testes**.
Ruff, mypy, oxlint e TypeScript passaram; o contrato OpenAPI e os tipos foram regenerados.

Os 16 cenários existentes de navegador (8 × desktop/celular) passaram. Os 4 cenários novos
(2 × desktop/celular) em `web/e2e/market-management.spec.ts` passaram: cadastro/edição/desativação
de uma filial em outra UF, contexto específico da rede, persistência da seleção com filtros,
ajuda em 320 px, varredura de overflow/conteúdo cortado e acessibilidade com axe.
As verificações de contraste usam movimento reduzido para medir a tela completa, sem capturar
um frame parcialmente transparente da animação de entrada.

Tudo usa API real e banco descartável com fontes simuladas. Não comprova cobertura de um CEP/ID
novo nos sites reais; a instalação Docker do zero não foi executada nesta verificação.

## Edição, busca direta e novas redes — 02/10/2026

- Backend determinístico: **177 testes passaram**, 6 ignorados (4 ao vivo e 2 de PostgreSQL).
- Vitest: **26 passaram**. Ruff/formatação, mypy, oxlint e TypeScript passaram.
- Playwright: os 20 cenários anteriores (uso e gestão regional) e os 6 novos cenários de edição,
  início direto e assistente passaram em desktop/celular. Os novos fluxos foram verificados
  novamente após a revalidação da fonte, incluindo larguras de 320 px e axe no diálogo.
- O backend testa o cadastro de uma rede independente e uma coleta completa pelo worker até a
  comparação, com HTTP simulado. Também testa origem/índice inválidos, fonte alterada entre
  prévia e cadastro, permissões/CSRF, confirmação, duplicidade e atualização do índice em todas
  as lojas sem mudar domínio ou disponibilidade.
- O transporte público tem testes de IP privado, DNS misto/rebinding, IP fixado com Host/SNI,
  tamanho de documento e redirecionamento de robots. Sitemaps têm limites de documentos/páginas
  e cache verificados; moedas, faixas/múltiplas ofertas e condições incompatíveis são recusadas.

O cenário do assistente no navegador simula as respostas de teste/cadastro; os testes de
integração verificam os endpoints reais e o transporte com fontes locais simuladas. Isso não
garante compatibilidade com um mercado real específico, nem executa implantação ou acesso ao vivo.


## Idioma, comparação por metro e revisão antes da busca — 02/10/2026

- Backend determinístico: **193 passaram**, 6 ignorados (4 ao vivo e 2 de PostgreSQL).
  Inclui leitura de rolos/comprimento total, equivalência por metro, compra de pacotes inteiros,
  coleta pelo adaptador genérico até a comparação e upgrade/downgrade com dados preservados.
- Vitest: **33 passaram**, incluindo persistência/tradução, formatos e ordenação do histórico.
  Ruff/formatação, mypy strict, oxlint e TypeScript passaram.
- Playwright: **32 passaram** (16 cenários × desktop/celular), cobrindo os 26 anteriores e
  os 6 novos de idioma/criação, seleção no início/revisão e ordenação de todas as colunas.
  Inclui ajuda/assistente em inglês a 320 px e acessibilidade/overflow dos novos fluxos.
- Fontes simuladas e bancos descartáveis. Nenhuma coleta real do Pradão, implantação nova ou
  teste PostgreSQL foi feito nesta rodada; preços reais e cobertura de entrega exigem validação
  da fonte na instalação. A matriz histórica de screenshots não foi regenerada.


### Papel higiênico no catálogo padrão

Incluído na categoria Higiene com ilustração local, comparação por metro e quantidade inicial
120 m. A ação de adicionar um item do catálogo respeita sua quantidade inicial quando o usuário
não fornece outra. O teste de integração cobre tanto produto personalizado quanto item padrão,
desde a adição à lista até coleta e comparação, sem HTTP real. Backend: **194 passaram**, 6
ignorados; lint/formatação e tipos dos arquivos alterados passaram.


### Atualização visual do README

Regenerada a matriz completa de **46 screenshots** da interface atual (10 telas × quatro
larguras e 6 imagens em modo escuro), com dados fictícios. O cenário `screens.spec.ts` passou
em 360/390/1280/1440 px, incluindo overflow, conteúdo cortado e verificações de acessibilidade
nas larguras cobertas. Foram geradas também 12 prévias de viewport para o README (seis em cada idioma),
sem cortar/editar as imagens completas. A galeria identifica explicitamente que as imagens não
são preços atuais. Os 32 cenários de uso passaram novamente antes da publicação, e os 33 testes
Vitest passaram.
