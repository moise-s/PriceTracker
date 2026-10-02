# Guia de uso

[English](user-guide.en.md)

## Sua conta e suas lojas

Peça uma conta ao administrador. Troque a senha temporária no primeiro acesso e guarde os
códigos de recuperação. O autocadastro fica desligado por padrão. Listas, produtos próprios,
preferências e histórico são pessoais; mercados e filiais são comuns à instalação.

Em **Mercados**, filtre por UF, cidade, bairro ou nome. **Mostrar só minhas lojas** facilita rever
a seleção. Os filtros só mudam a exibição; uma loja marcada em outra cidade continua selecionada.
Clique em **Salvar** para guardar a seleção. Com a lista pronta, **Verificar preços agora** salva
as lojas e inicia a busca diretamente, sem outra confirmação. O limite é 40 lojas por
seleção; começar com poucas evita buscas demoradas e deslocamentos irrelevantes.

Se faltar uma filial, o administrador pode adicioná-la em **Administração → Mercados**.
Se faltar a própria rede, consulte [cobertura e integrações](markets.md).

## Lista e perfil

Use o catálogo como ponto de partida. Crie produtos próprios quando não houver o item desejado,
com marca e tamanho adequados. A quantidade na lista é o que pretende comprar; a embalagem
descreve cada pacote. Exemplo: arroz em pacote de 1 kg, quantidade de 2 pacotes.

O lápis em **qualquer produto**, inclusive **Ovos 30 unidades**, permite editar nome, embalagem,
marca, regras de busca e imagem. A edição do catálogo cria uma cópia pessoal e não adiciona o
produto à lista automaticamente. Suas alterações aparecem nos cartões e na lista; o catálogo
original continua disponível para as outras pessoas. Nas palavras obrigatórias, vírgulas separam
grupos e `|` indica alternativas dentro de um grupo (ex.: `ovo | ovos, branco`).

Em **Perfil**, informe endereço e coordenadas e cadastre veículo, consumo e combustível se quiser
incluir deslocamento. O custo considera ida e volta; informe os pedágios também de ida e volta em
Mercados. Sem essas informações, desative o deslocamento para comparar só os produtos.
Distância estimada pode divergir do trajeto real, especialmente com pontes e serras.

Só habilite preços de clube nas redes em que tem cadastro. O aplicativo não faz login no clube
nem usa seu CPF. Consulte o limite de cada fonte antes de usar uma promoção no orçamento.

## Busca, comparação e histórico

Em **Mercados**, use **Verificar preços agora** no resumo acima das lojas ou na barra de seleção.
O resumo mostra quantos produtos e lojas serão consultados. Se já existe uma busca, o botão abre
o progresso. **Opções da busca e histórico** permite revisar a busca e alterar o uso opcional da
IA antes de iniciá-la. A ação rápida permite esse fallback, sujeito à configuração da instalação.
A busca roda em segundo plano; é possível fechar a página e voltar
enquanto o servidor e o worker continuam em execução. Veja cada resultado:

| Resultado | Significado / próxima ação |
| --- | --- |
| Encontrado | Confira equivalência, embalagem, preço e data |
| Não encontrado | O produto não apareceu na fonte; não significa preço zero ou ausência na loja física |
| Indisponível | A oferta está sem estoque na fonte |
| Sem preço | O produto foi identificado, mas sem preço utilizável |
| Bloqueado / tempo esgotado / falha na fonte | A coleta não concluiu; consulte a saúde da fonte e repita as falhas |
| Precisa de IA | A leitura determinística não conseguiu interpretar a fonte; fallback é opcional |

Em **Onde compensa**, a cesta comum compara os itens encontrados em todas as lojas; cobertura
mostra o que cada uma atende; o plano econômico considera cobertura, preços e deslocamento.
Uma cesta incompleta não deve ganhar por ter menos itens. Confira a confiança e os itens faltantes.
Preços antigos ficam fora da recomendação por padrão; permitir antigos exige avaliar sua data.

**Histórico** permite consultar preços anteriores. **Avisos** mostra alertas por preço-alvo;
**Agendamentos** cria buscas recorrentes enquanto os processos estiverem rodando. Se uma loja
for desativada pelo administrador, revise os agendamentos que a usam explicitamente.
Os agendamentos criados pela interface usam `America/Sao_Paulo` (horário de Brasília).
Se estiver em outro fuso, informe o horário equivalente; a escolha de fuso está no backlog.

## Ajuda e administração

O guia resumido está no app em **Mais → Como usar**. Administradores podem criar contas,
configurar filiais e consultar **Administração → Fontes**. Se a busca ficar na fila, confira o
worker; para diagnóstico técnico veja [operação local](operations.pt-BR.md).

A instalação padrão é local: não há hospedagem compartilhada, acesso remoto automático ou
comparação em outras moedas. Veja [primeiros passos](getting-started.md) para acesso e instalação.

## Atualizar preços pelo Início

Escolha as filiais na seção **Mercados da próxima verificação**, inclusive redes recém-cadastradas.
**Atualizar preços** salva a seleção e abre três passos: revisar produtos/quantidades na lista →
**Confirmar lista e escolher mercados** → confirmar lojas e **Verificar preços agora**.
Uma rede nova não fica selecionada automaticamente para todos os usuários.

## Idioma e criação de produtos

O seletor de idioma oferece português e inglês na tela de entrada, barra lateral e cabeçalho do
celular. A escolha fica neste navegador e não perde formulários abertos. Moeda continua BRL, endereços
continuam brasileiros e termos de busca seguem o idioma dos mercados. Após **Criar produto**, você
volta à lista e pode usar **Adicionar** no cartão; para editar novamente, use o lápis.

## Papel higiênico folha dupla por metro

Na lista, busque **Papel higiênico folha dupla** na categoria **Higiene** e clique em **Adicionar**.
O produto padrão começa com **120 m** e aceita qualquer tamanho de embalagem.
Para criar uma versão independente, em **Criar produto** escolha o modelo **Papel higiênico folha dupla**. Ele exige folha dupla, aceita
qualquer marca e ativa **Comparar qualquer tamanho pelo preço por metro**, com unidade **m**.
Informe quantos metros deseja (padrão 120 m), crie e use **Adicionar** no cartão. Essa metragem é a
quantidade inicial da lista. Os termos/regras podem ser ajustados para o idioma dos mercados.

4 rolos × 30 m = 120 m; 12 rolos × 30 m = 360 m. Por R$10 e R$24, respectivamente, os preços são
R$0,0833/m e R$0,0667/m. Folha dupla não dobra os metros. Comprimento ou número de rolos desconhecido
não é inventado; o anúncio fica fora da comparação. O menor preço por metro é exibido com quatro
casas decimais. A cesta compra **pacotes inteiros** suficientes para a metragem pedida: menor preço
por metro pode exigir mais gasto inicial ou comprar metros extras. Confira embalagem e notas do custo.
Para exigir tamanho fixo, desligue a opção de qualquer tamanho e ajuste tamanho/tolerância.
Os alertas continuam sendo por embalagem (não por metro).

## Ordenar o histórico

Em **Histórico de preços → Ver tabela**, clique em qualquer cabeçalho: Data, Loja, Anúncio, Preço,
Por unidade ou Situação. O primeiro clique ordena crescente e o próximo inverte; a seta mostra a
ordem. Valores sem preço ficam no fim nos dois sentidos. No celular, a tabela pode rolar lateralmente.
