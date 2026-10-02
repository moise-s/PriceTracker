# Começar com o PriceTracker

[English](getting-started.en.md)

Se alguém já instalou o PriceTracker para você, peça uma conta ao administrador e siga o
[guia de uso](user-guide.md). Estes passos são para quem vai manter sua própria instalação.

## Antes de instalar

- Confira [as redes integradas e seus limites](markets.md). Para outras redes, o assistente testa
  sites com preços públicos em BRL; fontes que dependem de login/CEP podem precisar de integração própria.
- Tenha Git, Docker com Compose v2 em execução, Python 3 e um terminal POSIX (Linux/macOS;
  Windows com WSL2 e integração do Docker). Python é usado pelo script que cria segredos;
  o backend e a interface rodam dentro dos containers.
- Confirme no terminal: `git --version`, `docker compose version` e `python3 --version`.
- Você não precisa de conta em provedor de IA, chave de API ou assinatura para as buscas normais.

## Instalar e criar sua conta

Primeiro obtenha um checkout da **v1** (`feat/rebuild-v1`) do
[repositório](https://github.com/moise-s/PriceTracker). Esta reconstrução ainda precisa ser
disponibilizada publicamente; a `main` local contém a v0. Se a branch v1 não estiver disponível
no repositório público, aguarde sua publicação ou obtenha o código v1 com o mantenedor.
Um clone da versão antiga não contém os serviços destes passos.

Na pasta do checkout v1, confira se existem `compose.yaml`, `backend/` e `web/`, então execute:

```bash
./scripts/init-secrets.sh
docker compose up -d --build
docker compose ps
```

A primeira execução baixa as imagens e compila a aplicação. Aguarde os serviços persistentes
ficarem `healthy`. O serviço `migrate` termina com código 0 depois de preparar o banco; ele
não precisa ficar em execução. Os comandos pressupõem a versão v1, com `compose.yaml`,
`backend/` e `web/`; um checkout do protótipo em `legacy/` usa instruções diferentes.

```bash
docker compose exec api pricetracker setup-code
```

Abra **http://localhost:8090**, no mesmo computador. Informe o código (válido por 30 minutos),
seu nome, usuário e uma senha com pelo menos 10 caracteres. Guarde os dez códigos de recuperação
mostrados na tela: não há recuperação por e-mail. Se o código expirar, gere outro.

Não é obrigatório criar `.env`; os padrões funcionam localmente. Se precisar mudar a porta,
copie `.env.example` para `.env` e ajuste **ambos** `PRICETRACKER_PORT` e
`PRICETRACKER_PUBLIC_ORIGIN` para o mesmo endereço. Recrie os serviços com `docker compose up -d`.
Use o endereço exato configurado, pois ele também protege as operações da API.

## Faça sua primeira comparação

1. **Administração → Mercados:** confira as redes e filiais. Cadastre uma filial ausente de uma
   rede integrada usando os dados oficiais descritos em [Mercados](markets.md). Para uma rede
   diferente, use **Adicionar novo mercado**, teste o site e revise a fonte antes de ativá-la.
2. **Mercados:** filtre por UF/cidade, escolha as lojas que visitaria e salve a seleção.
3. **Minha lista:** adicione dois ou três produtos para começar. Confira embalagem, marca e
   quantidade desejada; você também pode criar um produto próprio.
4. **Perfil:** endereço com coordenadas e veículo são opcionais. Para comparar só os produtos,
   desative o custo de deslocamento. Marque preços de clube apenas onde você é participante.
5. **Mercados → Verificar preços agora:** inicia diretamente. Para ajustar opções, abra
   **Buscar preços**. Acompanhe os resultados e abra **Onde compensa**.
6. Confira itens faltantes e a data dos preços. Uma loja com menos itens não ganha só porque o
   subtotal ficou menor. Preços online podem diferir da gôndola.

## Outras pessoas, reinícios e backup

Crie contas em **Administração → Usuários**. Cada pessoa recebe senha temporária, troca no
primeiro acesso e mantém lista, histórico e seleção próprios. Redes e filiais são comuns à instalação.

```bash
docker compose down       # para; preserva os volumes
docker compose up -d      # volta a executar
make backup               # se houver make; alternativa: ./scripts/backup.sh
```

Guarde os backups em local seguro; eles contêm dados da instalação. Não apague `secrets/` nem use
`docker compose down -v` para uma parada normal. Veja [operação, restauração e diagnóstico](operations.pt-BR.md).

O padrão só publica a interface em loopback. `localhost` no celular aponta para o celular,
não para seu computador. Acesso remoto/servidor é um trabalho separado e não está configurado aqui.

## Se algo não funcionar

| Sintoma | O que conferir |
| --- | --- |
| `python3: command not found` | Instale Python 3 no ambiente em que executa o script |
| Docker não conecta | Inicie o Docker; no Windows, confirme a integração com WSL2 |
| A porta 8090 está ocupada | Ajuste porta e origem juntas no `.env` |
| A página ainda não abre | `docker compose ps`; aguarde o build e os healthchecks |
| Não consigo criar o administrador | Gere outro código; se já há administrador, use Entrar ou peça uma conta |
| Busca fica na fila | `docker compose ps worker` e `docker compose logs --tail=100 worker` |
| Minha loja não aparece | Limpe filtros, confira se rede/filial estão ativas e peça o cadastro ao administrador |
| Tudo falha numa rede | Confira Administração → Fontes e o contexto oficial da filial; IA não corrige integração ausente |

Ao relatar um problema, envie a versão/branch, passos, status da busca e mensagem de erro.
Remova dados pessoais, cookies, códigos de configuração/recuperação e chaves dos logs.
