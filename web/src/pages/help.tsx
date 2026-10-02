import { translate, useLocale } from "@/lib/i18n";
import { Link } from "react-router";
import { useMe } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { Card, InlineAlert } from "@/components/ui";
import { buttonClass } from "@/components/ui/utils";

export function HelpPage() {
  useLocale();
  const me = useMe();
  const steps = [
    { to: "/mercados", title: "1. Escolha as lojas da sua região", text: "Filtre por UF, cidade ou nome. Selecione as filiais em que compraria e salve. A seleção é pessoal; o cadastro de redes e filiais é compartilhado nesta instalação." },
    { to: "/lista", title: "2. Monte a lista", text: "Adicione produtos do catálogo ou crie seus próprios produtos. O lápis permite editar qualquer produto; as mudanças são só suas. Confira marca, tamanho da embalagem e quantidade desejada: 2 unidades de 1 kg são diferentes de 2 kg de um produto vendido por peso." },
    { to: "/perfil", title: "3. Ajuste o deslocamento e os clubes", text: "Endereço com coordenadas e veículo são opcionais. Informe consumo, combustível e pedágios para incluir a viagem. Só marque preços de clube nas redes em que você tem cadastro." },
    { to: "/buscar", title: "4. Busque e confira os resultados", text: "Em Mercados, Verificar preços agora salva as lojas e inicia a busca diretamente. Buscar preços oferece opções e histórico. Acompanhe o progresso e confira os resultados: não encontrado, sem preço e bloqueado são diferentes. Repita falhas ou revise candidatos quando necessário." },
    { to: "/comparar", title: "5. Veja onde compensa", text: "Compare a cesta comum, a cobertura e o plano econômico. Confira itens faltantes, data dos preços e custo de ida e volta antes de decidir. O menor subtotal de uma cesta incompleta não representa a compra toda." },
  ];
  return <div className="mx-auto max-w-3xl space-y-5">
    <PageHeader title={translate("Como usar o PriceTracker")} description={translate("Da escolha das lojas à primeira comparação, com os limites dos preços visíveis.")} />
    <ol className="space-y-3">{steps.map((step) => <li key={step.to}><Card className="space-y-2 p-4"><h2 className="font-bold">{step.title}</h2><p className="text-sm text-ink-2">{translate(step.text)}</p><Link to={step.to} className={buttonClass({ variant: "secondary", size: "sm" })}>{translate("Abrir ")}{step.title.split(". ")[1]}</Link></Card></li>)}</ol>
    <InlineAlert tone="info" title={translate("Minha região tem outros mercados")}>{translate("A instalação inclui Angeloni, Bistek, Fort Atacadista e Imperatriz. Para uma rede diferente, o administrador pode usar Adicionar novo mercado: testa o site e um produto, revisa o preço público e cadastra a primeira loja. Sites compatíveis entram sem editar código; fontes com login, CEP ou formatos específicos podem exigir integração própria. A interface oferece português e inglês. Moeda (BRL), endereços brasileiros e fontes de preços seguem os limites desta instalação.")}{me.data?.user.role === "admin" ? <Link to="/admin" className="mt-2 block font-semibold underline">{translate("Abrir Administração → Mercados")}</Link> : null}
    </InlineAlert>
    <Card className="space-y-2 p-4"><h2 className="font-bold">{translate("Os preços são da minha loja?")}</h2><ul className="list-disc space-y-2 pl-5 text-sm text-ink-2"><li>{translate("Angeloni: região atendida pelo CEP, confirmada com o vendedor quando configurado.")}</li><li>{translate("Fort: loja online identificada pelo ID oficial.")}</li><li>{translate("Bistek: preço online de referência de Florianópolis/SC, compartilhado entre filiais. Confira a gôndola em outras cidades.")}</li><li>{translate("Imperatriz: somente ofertas vigentes do Super Clube; itens fora de oferta podem não aparecer.")}</li><li>{translate("Redes pelo assistente: referência online pública. Todas as filiais compartilham essa fonte, sem confirmar a região de entrega ou o preço da loja física.")}</li></ul><p className="text-sm text-ink-3">{translate("Preço online pode diferir da gôndola. Consulte as notas em Mercados. Preços antigos ficam fora da recomendação por padrão.")}</p></Card>
    <Card className="space-y-2 p-4"><h2 className="font-bold">{translate("Contas, acesso e problemas comuns")}</h2><p className="text-sm text-ink-2">{translate("Peça sua conta ao administrador da instalação. Guarde seus códigos de recuperação; eles permitem trocar a senha sem e-mail. Cada conta tem lista, preferências e histórico próprios.")}</p><p className="text-sm text-ink-2">{translate("Se a busca não avançar, o administrador deve conferir o worker. Se todas as fontes falharem, consulte Administração → Fontes. Sem coordenadas ou veículo, desative o deslocamento no Perfil para comparar só os produtos.")}</p><p className="text-sm text-ink-3">{translate("A instalação padrão funciona em localhost no computador onde está rodando. O endereço localhost do celular aponta para o próprio celular. Acesso remoto exige uma configuração separada.")}</p></Card>
  </div>;
}
