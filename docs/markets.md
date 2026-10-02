# Mercados, filiais e cobertura regional

[English](markets.en.md)

Uma **rede** tem uma integração de coleta (adaptador). Uma **filial** é uma loja física associada
a uma região de preços online. A **seleção pessoal** define quais filiais entram na sua comparação.
O administrador gerencia redes e filiais; cada usuário gerencia sua seleção.

## O que a versão atual atende

O cadastro inicial concentra-se em Santa Catarina e inclui filiais em outros estados. A aplicação
oferece português e inglês na interface e usa moeda BRL, CEP e UF brasileiros. Isso ainda não é suporte internacional.

| Rede | Como configura uma nova filial | O que os preços representam |
| --- | --- | --- |
| Angeloni | Nome, cidade/UF e CEP atendido; vendedor da região opcional | A região online resolvida pelo CEP. Se não houver cobertura ou o vendedor não corresponder, a busca informa erro de contexto |
| Fort Atacadista | Nome, cidade/UF e ID numérico oficial da loja online (`store_id`) | A loja online selecionada por esse ID |
| Bistek | Nome e cidade/UF; endereço e coordenadas opcionais | Referência online de Florianópolis/SC, compartilhada entre filiais; cadastrar uma loja em outro estado não muda o preço |
| Imperatriz | Nome, cidade/UF e ID numérico oficial da loja no Super Clube | Só ofertas vigentes daquela loja, com preço normal/clube separados; itens fora de oferta podem não aparecer |
| Nova rede pelo assistente | Site HTTPS, link de um produto, índice do site e primeira loja | Preço online público de referência em BRL; todas as filiais compartilham essa fonte, sem confirmar a região de entrega ou o preço da gôndola |

Use dados oficiais da rede. Para Fort e Imperatriz, o ID é o identificador usado pelo site, não
um número escolhido pelo administrador. Endereço físico, nome e coordenadas não bastam para
descobrir uma região de preços. Confira [a matriz de prontidão](sources/readiness-matrix.pt-BR.md).

## Configurar pela interface

1. Entre como administrador e abra **Administração → Mercados**.
2. **Editar mercado** permite corrigir nome, cor, notas e disponibilidade.
3. **Adicionar filial** mostra os campos e as instruções específicos da rede. Cadastre endereço
   e, se souber, latitude/longitude da loja para calcular distância. Coordenadas precisam vir juntas.
4. Expanda **gerenciar lojas** e use **Editar filial** para corrigir dados ou desativar uma loja.
5. Abra **Mercados**, filtre por UF/cidade e selecione as filiais que deseja usar.
6. Faça uma busca pequena e confira o resultado, o contexto e a fonte antes de confiar nos preços.

Desativar não apaga lojas, observações ou histórico. A rede/filial sai das novas seleções, buscas
e comparações. Preferências já salvas ficam ocultas enquanto a loja está indisponível; podem voltar
ao reativá-la se a pessoa não tiver substituído sua seleção nesse intervalo. Buscas já criadas
podem terminar. Agendamentos com lojas explícitas desativadas precisam ser revisados; essas
ocorrências são recusadas, em vez de coletar uma loja diferente silenciosamente.

Após registrar buscas, o CEP/vendedor ou ID que define a região de preços não pode ser trocado
no mesmo cadastro. Desative a filial antiga e crie outra para preservar a relação do histórico com
a região original. Nome, endereço e coordenadas podem ser corrigidos.

As configurações administrativas sobrevivem ao seed/reinício. Filiais editadas passam a ter
origem `admin` e não são sobrescritas pelo cadastro inicial. Metadados técnicos da integração
(adaptador, domínio e site) das quatro integrações iniciais continuam definidos em código.
Nas redes adicionadas pelo assistente, o domínio e a fonte validada ficam no banco e sobrevivem
a reinícios. Não são aceitos cookies, credenciais ou configurações HTTP arbitrárias.

## Minha cidade tem outra rede

Use **Administração → Mercados → Adicionar novo mercado**:

1. Cole o site oficial e o link de um produto que mostra preço sem login, ambos no mesmo domínio.
2. Clique em **Testar site**. O assistente respeita `robots.txt`, verifica o produto e o preço em
   reais e procura o índice de páginas automaticamente no `robots.txt` ou em `/sitemap.xml`.
   Se necessário, abra a opção de índice e informe o sitemap de produtos no mesmo domínio.
3. Confira o produto/preço de exemplo e a quantidade de páginas encontradas. Cadastre o nome e
   a cor da rede, a primeira loja e sua cidade/UF.
4. Confirme que aceita usar o preço online público de referência. **Cadastrar e ativar mercado**
   testa a fonte novamente antes de salvar a rede e a primeira loja juntas.
5. Selecione a loja em **Mercados**, faça uma verificação pequena e confira as fontes.
   Depois, complete o endereço/coordenadas em **Editar filial** ou adicione outras lojas.

Se o site mudar o índice, use **Revalidar fonte** no cartão da rede: informe um produto atual e
o novo sitemap, teste e confirme. Uma falha preserva a configuração anterior. O índice é
atualizado em todas as filiais, sem reativar lojas desativadas. O domínio continua o mesmo;
trocar de site exige cadastrar outra rede para preservar a origem do histórico.

O coletor usa [JSON-LD Product/Offer](https://schema.org/Offer) e
[sitemaps XML](https://www.sitemaps.org/protocol.html). Aceita uma oferta com preço explícito em
BRL por página; não interpreta faixas de preço, múltiplas ofertas, ofertas vencidas ou condições
por quantidade/tipo de cliente. A equivalência e a embalagem continuam sendo conferidas pelo
matching do aplicativo; um exemplo válido não garante a cobertura de toda a sua lista.

A descoberta lê no máximo 6 sitemaps e 5.000 páginas por índice, com cache de 24 horas.
Cada busca testa até 6 candidatos descobertos, além dos links preferidos, dentro do limite do
produto. Sites grandes podem precisar do sitemap específico de produtos. URLs numéricas sem
nomes úteis têm descoberta limitada; os links preferidos ajudam após revisar um anúncio.
O teste inicial tem prazo de 35 segundos e documentos são limitados a 4 MB.

Não configura CEP, filial, clube ou login no site e não executa JavaScript. O nome/cidade da loja
não muda a região do preço. Se o teste falhar, o cadastro não é ativado: ajuste os links ou siga
[Contribuir com um novo mercado](../CONTRIBUTING.pt-BR.md#nova-integração-de-mercado).
Ainda não há entrada manual de preços; uma fonte sem dados públicos compatíveis exige outra integração.

Ao sugerir uma rede, informe nome, site oficial, cidade/UF e se o preço depende de filial/CEP/clube.
Não envie CPF, cookies, logins ou chaves. Uma fonte sem preços públicos utilizáveis pode exigir
outra abordagem; o app deve declarar a ausência de cobertura.

## Por trás do cadastro de uma rede nova (ex.: Pradão)

**O assistente não usa LLM e não gera código de coleta.** Uma rede compatível reutiliza o adaptador
`public_jsonld`, já implementado. O cadastro salva a configuração que aponta esse código para o site.

1. A UI envia site, produto de exemplo e sitemap opcional para
   `POST /api/v1/admin/markets/probe`, com autenticação de administrador e proteção CSRF.
2. O backend valida HTTPS público e o mesmo domínio, inclusive o IP da conexão e redirecionamentos;
   recusa destinos privados/locais e documentos grandes. Respeita `robots.txt`, intervalos e timeout.
3. Lê o HTML sem executar JavaScript ou entrar em conta. Exige um JSON-LD **Product** e uma única
   **Offer**, com nome e preço numérico positivo em **BRL**. Não aceita faixas, várias ofertas,
   condições de quantidade/cliente nem oferta vencida.
4. Descobre o sitemap no `robots.txt`, tenta `/sitemap.xml` ou usa o índice informado. A leitura é
   limitada a **6 mapas e 5.000 páginas**. O produto de exemplo precisa aparecer nesse índice.
5. Mostra nome, preço, páginas descobertas e o limite da referência online. Ao confirmar o cadastro,
   `POST /api/v1/admin/markets` testa novamente e cria a rede e primeira filial. Guarda
   `adapter_key=public_jsonld`, domínio permitido, site e sitemap no contexto de preços da filial.

Na busca seguinte, o worker carrega o índice (cache de até 24 horas), usa os termos/regras do produto
para ordenar os slugs das URLs e visita até seis candidatos vindos do sitemap, dentro do limite da
busca. Também considera links preferidos do mesmo domínio. Extrai o JSON-LD, identifica embalagem,
aplica palavras obrigatórias/exclusões/marca/tamanho e escolhe o anúncio equivalente disponível com
menor preço comparável. Salva observações com fonte, método e data para comparação e histórico.
Um índice só com URLs numéricas pode validar o exemplo e ainda assim não permitir encontrar outros
produtos pelo nome. Validar um exemplo não comprova cobertura de todos os itens.

Cadastrar a cidade não muda a região de preços: nesta integração, todas as filiais compartilham a
**referência online pública**, que não confirma gôndola ou entrega. Cada pessoa escolhe a nova filial
no **Início** ou em **Mercados**; o cadastro administrativo não seleciona lojas para todas as contas.
No Início, **Atualizar preços** salva a seleção e abre lista → confirmação dos mercados → busca.

A IA opcional do worker é um fallback de extração quando um adaptador solicita IA e fornece um trecho da página, existe provedor
configurado e a busca permite IA. Ela não participa da validação do cadastro, não transforma um site
incompatível em fonte válida, não configura CEP/login e não substitui uma integração específica.
O adaptador genérico não solicita esse fallback: página incompatível resulta em falha na fonte.
Resultados de IA são conferidos contra a página e continuam sujeitos às regras de equivalência.

Sites com login, preços por CEP/vendedor, dados só em JavaScript, formatos próprios ou moeda diferente
precisam de um adaptador específico e testes com fixtures. O roteiro de contribuição está em
[guia de contribuição](../CONTRIBUTING.pt-BR.md). Para fontes genéricas, **Revalidar fonte** atualiza o sitemap de
todas as filiais após novo teste; mantém o domínio para preservar a origem do histórico. Falha no
teste preserva a configuração anterior.

Veja também a [explicação técnica em inglês](markets.en.md), com exemplo da configuração armazenada.
