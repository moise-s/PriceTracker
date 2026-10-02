# Operação local

Tudo roda na sua máquina com Docker Compose. Só a interface web é publicada, e só em loopback
(`http://localhost:8090`). Implantação em servidor e Tailscale Serve ficam fora do escopo desta
versão (decisão do dono do projeto).

## 1. Primeira instalação

```bash
./scripts/init-secrets.sh                    # cria ./secrets (senha do banco e chave da aplicação)
./scripts/init-secrets.sh --import-groq .env # opcional: copia a GROQ_API_KEY de um .env, sem exibir
docker compose up -d --build                 # db → migrate (migrations + seed) → api, worker, scheduler, web
docker compose ps                            # todos devem ficar "healthy"
```

- `./secrets/` fica fora do Git, com permissão `0600`. Arquivos: `postgres_password`,
  `app_secret_key`, `groq_api_key` e `openai_api_key` (os dois últimos podem ficar vazios; sem chave o
  fallback de IA fica desligado e o resto funciona).
- Configurações opcionais: copie `.env.example` para `.env` (ou use `--env-file`). Os padrões já são
  seguros para uso local. Atenção: o `.env` antigo da raiz (protótipo) é lido pelo Compose se
  existir; ele só é usado para as variáveis listadas no `compose.yaml`.

## 2. Primeiro acesso (criar o administrador)

Não existe senha padrão. Gere um código de uso único (válido por 30 minutos):

```bash
docker compose exec api pricetracker setup-code
```

Abra `http://localhost:8090`, informe o código, seu nome, usuário e uma senha (mínimo de
10 caracteres). A tela seguinte mostra **10 códigos de recuperação** uma única vez — guarde-os (é o
jeito de recuperar a senha, porque não há e-mail). Depois do bootstrap o autocadastro fica
desligado; o administrador cria contas em **Administração** (senha temporária com troca
obrigatória) ou liga o autocadastro.

Alternativa pela linha de comando (senha lida do terminal, sem eco; troca obrigatória no primeiro
acesso): `docker compose exec api pricetracker user create --username <usuario> --display-name "<nome>" --admin`.

## 3. Uso diário

- Para preparar outras regiões: **Administração → Mercados** cadastra e corrige filiais das
  redes integradas e controla sua disponibilidade. **Mercados** filtra por UF/cidade e guarda a
  seleção de cada pessoa. Veja [cobertura e contextos de preços](markets.md).
- Guia para novos usuários: [primeiros passos](getting-started.md), [uso diário](user-guide.md) e
  **Mais → Como usar** no app.
- Monte a lista, escolha as lojas, cadastre endereço (coordenadas ou "usar minha localização") e
  veículo, e clique em **Buscar preços**. A busca roda em segundo plano; pode fechar a página.
- **Agendamentos** mantém os preços frescos (ex.: toda sexta às 7h).
- **Avisos** mostra alertas de preço disparados pelas buscas.
- Linha de comando (saída JSON; códigos de saída 0 sucesso, 4 parcial, 5 falhou, 6 cancelada):
  `docker compose exec api pricetracker run --user <usuario> --store angeloni:beira-mar --product arroz`
  (`--enqueue` só enfileira para o worker; `--no-llm` desliga o fallback de IA).

## 4. Saúde e logs

```bash
docker compose ps
docker compose logs -f --tail=100 api worker   # logs JSON com request_id/run_id, sem segredos
curl -s localhost:8090/api/v1/health/ready      # {"status":"ok","database":true,"schema_version":"0002"}
docker compose exec api pricetracker llm check  # testa o provedor de IA sem mostrar a chave
```

A página **Administração** mostra, por mercado, taxa de sucesso, duração, métodos de extração e
falhas dos últimos 14 dias, além do uso de IA.

## 5. Backup e restauração

```bash
make backup                                               # = ./scripts/backup.sh → ./backups/pricetracker-<UTC>/
make restore-drill BACKUP=backups/pricetracker-<UTC>      # restaura num PostgreSQL descartável e confere
./scripts/restore.sh backups/pricetracker-<UTC> --yes     # DESTRUTIVO: substitui banco e imagens da stack
```

- O backup contém `db.dump` (formato custom do `pg_dump`), `uploads.tar.gz` (imagens enviadas) e
  `manifest.json` (sha256, versão do schema e contagens de linhas).
- O drill confere checksums, restaura, compara schema e contagens e verifica os arquivos de imagem,
  sem tocar na stack. O `restore.sh` roda o drill antes de apagar qualquer coisa.
- Evidência de 27/09/2026: backup `20260927T213829Z` (1,1 MB de dump, 11 imagens), drill **PASS** em
  3,8 s; restauração real removeu uma lista criada depois do backup e manteve a imagem enviada.
- Não há backup automático na instalação local: agende `make backup` (cron/launchd) se quiser.

## 6. Reinícios e persistência

`docker compose down` seguido de `docker compose up -d` preserva tudo (volumes `pg_data` e
`app_data`). Uma busca interrompida volta para a fila e é retomada do ponto em que parou.
O seed preserva nome, cor, notas e disponibilidade de mercados; filiais editadas pela
administração têm origem `admin` e não são sobrescritas. Domínios e adaptadores das quatro redes iniciais são mantidos em código.
Redes do assistente preservam domínio e fonte validados no banco; veja [fontes](markets.md).
Teste de 27/09: run com 19 de 40 alvos prontos → `down`/`up` → retomado (tentativa 2, 21 pendentes)
→ `success`, 29 observações, nenhuma duplicada. Para apagar **tudo** (inclusive dados):
`docker compose down -v`.

## 7. Atualização e migrations

```bash
git pull   # quando houver novas versões
docker compose up -d --build   # o job migrate aplica migrations pendentes e o seed idempotente
```

A revisão `0002` permite quantidades em metros sem apagar dados existentes. Instalações v1
precisam aplicá-la antes de usar a comparação por metro; o job `migrate` aplica no início.
Detalhes e limites de downgrade em [migrations](migrations.md).

## 8. Consumo de recursos (medido em 27/09/2026, Docker Desktop, Apple Silicon)

| Serviço | Em repouso | Durante uma coleta (40 alvos) | Limite configurado |
| --- | --- | --- | --- |
| api | ~90 MiB, ~0% CPU | ~91 MiB, picos de ~14% CPU | 1 CPU / 512 MiB |
| worker | ~70 MiB, ~0% CPU | 95–130 MiB, picos de ~23% CPU | 1 CPU / 768 MiB |
| scheduler | ~67 MiB | ~67 MiB | 0,25 CPU / 256 MiB |
| db | ~45–50 MiB | ~49 MiB | 1 CPU / 512 MiB |
| web | ~14 MiB | ~14 MiB | 0,5 CPU / 128 MiB |
| **Total** | **~290 MiB** | **~350 MiB** | |

Não há navegador headless: a coleta usa HTTP simples. Imagens: backend 432 MB, web 82 MB. A
concorrência do worker é `PRICETRACKER_WORKER_CONCURRENCY` (padrão 3), e cada host recebe no máximo
2 conexões.

## 9. Problemas conhecidos

- **Service worker em navegadores embutidos:** alguns navegadores baseados em Electron recusam o
  registro do service worker em `http://localhost` ("unknown error when fetching the script"). Em
  Chrome, Edge, Firefox e Safari ele registra normalmente (verificado com Chrome via Playwright). O
  app funciona sem ele; só perde o cache offline do shell.
- **Cookies `Secure` em HTTP:** navegadores atuais aceitam cookies `Secure` em `http://localhost`.
  Se acessar por outro nome/IP sem HTTPS, o login não persiste — use `localhost` ou um proxy HTTPS.
- **Uso a partir de outros dispositivos:** a porta está presa em `127.0.0.1`. Publicar na rede
  exige um proxy HTTPS (ex.: Tailscale Serve) e ajustar `PRICETRACKER_PUBLIC_ORIGIN` — fora do escopo
  desta versão.

## 10. Desenvolvimento sem Docker

```bash
make bootstrap   # uv sync + npm ci
make dev-db      # PostgreSQL descartável em 127.0.0.1:55433 (+ banco pricetracker_test)
make api         # API em :8000 (cookies sem Secure para http://localhost:5173)
make worker
make web         # Vite em :5173 com proxy /api → :8000
```
