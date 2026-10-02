# Contribuir com o PriceTracker

O código tem licença MIT. Correções de usabilidade, documentação, acessibilidade e integrações
de outras regiões são bem-vindas. Leia [arquitetura](docs/architecture.md),
[decisões](docs/decisions.md) e [cobertura](docs/markets.md) antes de alterar comportamento de preços.

## Ambiente local

Use Python 3.13+, uv, Node 22.12+ (ou posterior compatível com o Vite instalado), npm, Docker
com Compose v2 e make. Execute na raiz do repositório:

```bash
make bootstrap
make dev-db
make dev-init
make dev-setup-code
```

Depois, em terminais separados: `make api`, `make worker` e `make web`. Opcionalmente execute
`make scheduler` para recorrências. Abra **http://localhost:5173** e crie o administrador com o
código gerado. Os alvos de desenvolvimento fixam banco, ambiente e origem para não herdarem
acidentalmente a configuração de produção de `.env`.

`make dev-db` cria um PostgreSQL descartável chamado `pricetracker-dev-pg` na porta 55433.
Se esse container já existe, inicie-o com `docker start pricetracker-dev-pg`; não execute novamente
o alvo de criação. Não use seu banco pessoal para os testes: a suíte PostgreSQL recria o schema.

```bash
make lint
make typecheck
make test
make openapi       # se o contrato da API mudou; atualiza os dois arquivos gerados
make e2e           # Chrome instalado; backend com fixtures, sem acesso às redes reais
```

`make check` também exige `gitleaks` instalado. Testes ao vivo são opt-in: `make test-live` faz
requisições aos sites reais. Veja [testes e fixtures](docs/testing.md). Inclua o resultado dos
checks e passos para reproduzir a mudança. Nunca inclua `.env`, banco, dumps, imagens pessoais,
cookies, tokens ou credenciais em uma contribuição.

## Nova integração de mercado

Antes de escrever um adaptador, teste **Administração → Mercados → Adicionar novo mercado**.
Se a rede publica um produto com oferta única em BRL e sitemap utilizável, o coletor público
pode atender sem código específico. Veja [contrato, cobertura e limites](docs/markets.md).
Siga o roteiro abaixo quando a fonte exigir região, promoções específicas ou outro formato.

Uma integração específica precisa de código e evidência antes de ser oferecida na interface. Não clone o adaptador
de outra rede supondo que o site usa a mesma plataforma ou os mesmos identificadores.

1. Identifique a fonte oficial e pública, regras de acesso e `robots.txt`. Documente como o preço
   depende de CEP/filial/vendedor, se há cobertura parcial, e quais promoções são utilizáveis.
   Não contorne bloqueios, login obrigatório ou CAPTCHA.
2. Implemente `MarketAdapter` em `backend/src/pricetracker/adapters/<rede>.py`. O contrato recebe
   `AdapterContext` + `SearchQuery` e devolve `SearchOutcome` com `Listing`s. Use `PoliteClient`,
   `DocumentCache`, domínios permitidos explícitos e dinheiro como `Decimal`.
3. Mantenha extração separada de equivalência: o adaptador devolve candidatos, e o domínio decide
   se atendem ao produto. Preserve preço normal, promocional, clube, unidade/embalagem, estoque,
   URL e ID; nunca invente preço, região ou produto ausente.
4. Registre em `adapters/registry.py`; adicione a rede em `seed/MARKETS` e filiais verificadas em
   `seed/stores.json`. O slug deve ser estável; o domínio/URL técnico pertence ao código.
5. Defina os campos de região e a nota de cobertura em `services/markets.py` (`CONTEXTS`,
   `PRICE_NOTES`, `save_store`). A UI administrativa atende CEP/vendedor, ID numérico ou preço
   compartilhado. Para um contexto diferente, amplie schemas, formulário e validação juntos;
   não exponha configuração HTTP/URLs arbitrárias ao formulário.
6. Capture fixtures sanitizadas em `tests/fixtures/<rede>/` e escreva testes de contrato para
   produto encontrado, ausente, sem estoque, sem preço, embalagem/peso, promoções, contexto
   inválido e duas regiões com preços distintos (quando aplicável). Use transportes falsos para
   confirmar domínios, limites e respeito ao robots sem tráfego externo.
7. Teste worker, isolamento entre contas, comparação e administração. Atualize contrato com
   `make openapi` se necessário. Nomes/cor e preços de clube usam dados da API; confira a nova
   identidade nos gráficos e no modo escuro.
8. Atualize `docs/markets.md`, a ajuda no app, a matriz de prontidão e testes E2E/fakes.
   Marque limitações e diferencie testes determinísticos de verificações ao vivo autorizadas.

Uma filial pode ser configurada sem alterar código quando a rede já é integrada e seu contexto
é suportado. Para trocar a região de uma filial com buscas, crie outro cadastro e preserve o antigo.

## O que vem depois

Veja [backlog](docs/backlog.md). Prioridades para ampliar o público: modo de preços manuais para
redes sem fonte integrada, importação/exportação, pacote regional de filiais e moeda/fuso
configuráveis: essas melhorias futuras ainda não estão implementadas.
A interface já permite português e inglês; mantenha o catálogo de traduções atualizado.
