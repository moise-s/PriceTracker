# Riscos restantes e backlog priorizado

## Riscos

| Risco | Impacto | Mitigação atual | Próximo passo |
| --- | --- | --- | --- |
| **Imperatriz com cobertura parcial** (só ofertas do Super Clube) | Itens fora de oferta nunca aparecem nesse mercado | Status "não encontrado" com a nota de cobertura; sem vencedor injusto | Decisão do usuário (ver `sources/readiness-matrix.md`) |
| **Bistek com preço único** (site não deixa escolher filial) | Se as lojas tiverem preços diferentes na gôndola, a comparação usa o preço online de referência | Nota explícita em mercados/comparação; consulta única para todas as filiais | Reavaliar se o site passar a expor preço por loja |
| **Sites mudam** (layout, APIs, cookies de loja) | Adaptador para de encontrar produtos | Status tipado (`adapter_error`, `store_context_error`, `no_prices_extracted`), painel de saúde, fixtures + testes de contrato, smoke ao vivo | Rodar `make test-live` semanalmente; canário agendado (backlog) |
| **Distância estimada** (`haversine × 1,35`) | Pode errar em trajetos com ponte/serra e mudar um empate | Método e fórmula visíveis; OSRM opcional | Documentar/automatizar um OSRM local de SC |
| **Geocodificação manual** | O usuário precisa informar coordenadas ou usar a localização do navegador | Botão "usar minha localização"; Nominatim opcional com cache | Busca de CEP autorizada (backlog) |
| **LLM** (limites do Groq free tier, troca de modelos) | Fallback indisponível | Determinístico primeiro (0 chamadas nas execuções reais), `llm check`, falha só nos alvos afetados | Nenhum urgente |
| **Backup manual** | Perda de dados se o disco falhar | `make backup` + drill testado | Agendar backup com retenção (backlog) |
| **Service worker em navegadores embutidos** | Sem cache offline do shell nesses navegadores | App funciona sem SW; navegadores comuns registram normalmente | — |
| **Acesso só em `localhost`** | Não dá para usar pelo celular na rede | Intencional (escopo local) | Proxy HTTPS/Tailscale quando o dono quiser |

## Backlog priorizado

### P1 — próximos
1. **Decisão sobre o Imperatriz** e ajuste correspondente (manter/desativar/nova fonte autorizada).
2. **Backup agendado** com retenção (ex.: diário, 7 cópias) e alerta de falha.
3. **Canário semanal** agendado pelo scheduler (1 produto por mercado) alimentando o painel de saúde.
4. **Alerta de troca de mercado**: avisar quando o plano da semana economizar mais que um limite
   definido pelo usuário em relação à loja de costume (os alertas por preço-alvo já existem).
5. **Duplicar lista / listas recorrentes** na interface (a API já suporta `copy_from`).
6. **Modo "na loja"**: marcar itens comprados no celular (a API já tem `checked` por item).

### P2 — depois
7. **Residência compartilhada** (household) com permissões claras entre moradores.
8. **Exportação CSV/JSON** da lista, comparação e histórico; link de compra por mercado.
9. **Custo do tempo** como parâmetro opcional do plano (R$/hora), sempre visível.
10. **Rotas reais por padrão** com OSRM local e mais de 3 paradas quando fizer sentido.
11. **Sugestões pelo histórico** (itens frequentes, substitutos aceitos).
12. **Implantação em servidor** (Compose no homeserver + Tailscale Serve + backups remotos).
13. **Imagem do backend menor** (hoje 432 MB): wheels multi-stage mais enxutas.

### Já entregue além do P0
Agendamentos, cesta comum × cobertura × plano econômico, alertas de preço com avisos no app,
painel de saúde/admin, repetição só das falhas, teste seguro do provedor de IA, PWA, divisão ótima
entre até 3 lojas com rota exata, mediana e mínimo histórico por loja, sinalização de preço atípico,
pedágios por loja.
