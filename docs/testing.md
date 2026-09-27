# Testes e evidências

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
| Backend em SQLite | **125 passaram**, 6 pulados (4 ao vivo, 2 exclusivos de PostgreSQL) |
| Backend em PostgreSQL 17.10 | **127 passaram**, 4 pulados (ao vivo) |
| Smoke ao vivo (`--live`) | **4 passaram** (22:27–22:29 UTC): Angeloni, Bistek e Fort com embalagem/peso/unidade; ofertas do Imperatriz |
| Web unitários (Vitest) | **26 passaram** |
| E2E (Playwright) | **17 passaram**: 8 cenários × desktop (1280×900) e mobile (390×844) + matriz de telas |
| Lint e tipos | ruff, mypy strict, oxlint e tsc sem avisos |
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
