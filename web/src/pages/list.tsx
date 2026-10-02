import { translate, useLocale } from "@/lib/i18n";
import { ArrowRight, Heart, PackagePlus, Pencil, Plus, Search, ShoppingBasket, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import type { Schemas } from "@/api/client";
import { useAddToList, useCatalog, useDefaultList, usePersonalizeProduct, useProducts, useRemoveListItem, useUpdateListItem } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { ProductImage } from "@/components/domain";
import { Button, Card, EmptyState, ErrorState, Input, LoadingBlock, Select, Stepper } from "@/components/ui";
import { buttonClass, cn } from "@/components/ui/utils";
import { packageLabel, pluralize } from "@/lib/format";
import { UNIT_OPTIONS } from "@/lib/labels";

type CardModel = {
  key: string;
  name: string;
  category: string;
  image?: Schemas["ImageRef"] | null;
  pkg: string;
  catalogItemId?: string;
  productId?: string;
  favorite?: boolean;
  custom?: boolean;
  initialQuantity?: string;
  initialUnit?: Schemas["Unit"];
  item?: Schemas["ListItemOut"];
};

const STEP: Record<string, number> = { m: 30, kg: 0.5, g: 100, l: 1, ml: 100, un: 1, pct: 1 };

function normalize(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function ItemControls({ listId, item, compact }: { listId: string; item: Schemas["ListItemOut"]; compact?: boolean }) {
  useLocale();
  const update = useUpdateListItem();
  const remove = useRemoveListItem();
  const quantity = Number(item.quantity);
  const step = STEP[item.unit] ?? 1;
  return (
    <div className={cn("flex flex-wrap items-center gap-2", compact && "mt-2")}>
      <Stepper
        label={translate(`quantidade de ${item.product_name}`)}
        value={quantity}
        step={step}
        min={0}
        onChange={(value) => {
          if (value <= 0) remove.mutate({ listId, itemId: item.id });
          else update.mutate({ listId, itemId: item.id, body: { quantity: String(value) } });
        }}
      />
      {item.allowed_units.length > 1 ? (
        <Select aria-label={translate(`Unidade de ${item.product_name}`)} className="h-9 w-auto max-w-full rounded-full py-0 pr-9 pl-3 text-sm" value={item.unit} onChange={(e) => update.mutate({ listId, itemId: item.id, body: { unit: e.target.value as Schemas["Unit"] } })}>
          {item.allowed_units.map((unit) => (
            <option key={unit} value={unit}>
              {translate(UNIT_OPTIONS[unit] ?? unit)}
            </option>
          ))}
        </Select>
      ) : (
        <span className="text-sm text-ink-3">{translate(UNIT_OPTIONS[item.unit] ?? item.unit)}</span>
      )}
    </div>
  );
}

function ProductCard({ model, listId }: { model: CardModel; listId: string }) {
  useLocale();
  const add = useAddToList();
  const personalize = usePersonalizeProduct();
  const navigate = useNavigate();
  const inList = Boolean(model.item);
  return (
    <li>
      <Card className={cn("flex h-full min-w-0 flex-col gap-3 p-2 transition-shadow hover:shadow-lift sm:p-3", inList && "ring-2 ring-brand/40")}>
        <div className="relative">
          <ProductImage image={model.image} category={model.category} name={model.name} />
          {model.custom ? <span className="absolute top-2 left-2 rounded-full bg-surface/90 px-2 py-0.5 text-[11px] font-bold text-ink-2">{translate("Meu produto")}</span> : null}
          <button type="button" disabled={personalize.isPending} onClick={async () => {
            if (model.productId) navigate(`/produtos/${model.productId}`);
            else if (model.catalogItemId) {
              try { const product = await personalize.mutateAsync(model.catalogItemId); navigate(`/produtos/${product.id}`); } catch { /* The hook displays the error. */ }
            }
          }} className="absolute top-2 right-2 grid size-9 place-content-center rounded-full bg-surface/90 text-ink-2 hover:text-ink" aria-label={translate(`Editar ${model.name}`)}>
              <Pencil aria-hidden className="size-4" />
          </button>
        </div>
        <div className="flex-1">
          <p className="leading-snug font-semibold">{model.name}</p>
          <p className="text-sm text-ink-3">{model.pkg}</p>
        </div>
        {model.item ? (
          <ItemControls listId={listId} item={model.item} />
        ) : (
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            loading={add.isPending}
            aria-label={translate(`Adicionar ${model.name}`)}
            onClick={() => add.mutate({ listId, body: model.catalogItemId ? { catalog_item_id: model.catalogItemId } : { product_id: model.productId, quantity: model.initialQuantity, unit: model.initialUnit } })}
          >
            <Plus aria-hidden className="size-4" />{translate(" Adicionar")}</Button>
        )}
      </Card>
    </li>
  );
}

export function ListPage() {
  useLocale();
  const [searchParams] = useSearchParams();
  const priceCheckFlow = searchParams.get("flow") === "price-check";
  const createProductPath = priceCheckFlow ? "/produtos/novo?flow=price-check" : "/produtos/novo";
  const marketsPath = priceCheckFlow ? "/mercados?flow=price-check" : "/mercados";
  const catalog = useCatalog();
  const products = useProducts();
  const { list, isLoading: listLoading, error: listError, refetch } = useDefaultList();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("todos");

  const cards = useMemo<CardModel[]>(() => {
    const itemsByProduct = new Map((list?.items ?? []).map((item) => [item.product_id, item]));
    const ownProducts = new Map((products.data ?? []).map((p) => [p.id, p]));
    const fromCatalog: CardModel[] = (catalog.data?.items ?? []).map((item) => {
      const own = item.my_product_id ? ownProducts.get(item.my_product_id) : undefined;
      return {
        key: `c-${item.id}`,
        name: own?.name ?? item.name,
        category: own?.category ?? item.category,
        image: own ? own.image : item.image,
        pkg: own ? packageLabel(own.package_quantity, own.package_unit, own.sold_by) : packageLabel(item.package_quantity, item.package_unit, item.sold_by),
        catalogItemId: item.id,
        productId: item.my_product_id ?? undefined,
        item: item.my_product_id ? itemsByProduct.get(item.my_product_id) : undefined,
      };
    });
    const custom: CardModel[] = (products.data ?? [])
      .filter((p) => p.is_custom && p.is_active)
      .map((p) => ({
        key: `p-${p.id}`,
        name: p.name,
        category: p.category,
        image: p.image,
        pkg: packageLabel(p.package_quantity, p.package_unit, p.sold_by),
        productId: p.id,
        favorite: p.is_favorite,
        custom: true,
        initialQuantity: p.default_unit === "m" ? String(p.package_quantity ?? 120) : undefined,
        initialUnit: p.default_unit as Schemas["Unit"],
        item: itemsByProduct.get(p.id),
      }));
    return [...custom, ...fromCatalog];
  }, [catalog.data, products.data, list]);

  const categories = useMemo(() => Array.from(new Set(cards.map((c) => c.category))).sort(), [cards]);
  const filtered = cards.filter((card) => {
    if (category === "na-lista" && !card.item) return false;
    if (category !== "todos" && category !== "na-lista" && card.category !== category) return false;
    return !query || normalize(card.name).includes(normalize(query));
  });

  if (catalog.isLoading || listLoading || products.isLoading) {
    return (
      <>
        <PageHeader title={translate("Monte sua lista")} />
        <LoadingBlock label={translate("Carregando catálogo")} rows={4} />
      </>
    );
  }
  if (catalog.error || products.error || listError || !list) {
    return (
      <>
        <PageHeader title={translate("Monte sua lista")} />
        <ErrorState error={translate("Não foi possível carregar o catálogo ou a lista.")} onRetry={() => void refetch()} />
      </>
    );
  }

  const count = list.item_count;
  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-6">
      <div className="min-w-0">
        {priceCheckFlow ? <Card className="mb-5 space-y-3 p-4">
          <h2 className="font-semibold">{translate("1 de 3 · Revise sua lista")}</h2>
          <p className="text-sm text-ink-2">{translate("Confira os produtos e quantidades antes de escolher onde buscar.")}</p>
          <Link to={marketsPath} className={buttonClass({ variant: "primary", className: "max-w-full whitespace-normal" })}>{translate("Confirmar lista e escolher mercados ")}<ArrowRight aria-hidden className="size-4 shrink-0" /></Link>
        </Card> : null}
        <PageHeader
          title={translate("Monte sua lista")}
          description={translate("Escolha no catálogo ou crie seus próprios produtos. Quantidade da lista e tamanho da embalagem são coisas diferentes: 2 pacotes de 1 kg custam duas vezes o pacote.")}
          actions={
            <Link to={createProductPath} className={buttonClass({ variant: "secondary" })}>
              <PackagePlus aria-hidden className="size-4" />{translate(" Criar produto")}</Link>
          }
        />
        <div className="sticky top-14 z-20 -mx-4 space-y-3 bg-canvas/95 px-4 pt-1 pb-3 backdrop-blur lg:top-0 lg:mx-0 lg:px-0">
          <div className="relative">
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-ink-3" />
            <Input type="search" placeholder={translate("Buscar produto")} aria-label={translate("Buscar produto")} value={query} onChange={(e) => setQuery(e.target.value)} className="rounded-full pl-10" />
          </div>
          <div className="scrollbar-none -mx-4 flex gap-2 overflow-x-auto px-4 lg:mx-0 lg:px-0" role="group" aria-label={translate("Filtrar por categoria")}>
            {[{ id: "todos", label: "Todos" }, { id: "na-lista", label: `Na lista (${count})` }, ...categories.map((c) => ({ id: c, label: c }))].map((chip) => (
              <button
                key={chip.id}
                type="button"
                onClick={() => setCategory(chip.id)}
                aria-pressed={category === chip.id}
                className={cn("h-9 shrink-0 rounded-full px-4 text-sm font-semibold ring-1 transition-colors", category === chip.id ? "bg-ink text-canvas ring-ink" : "bg-surface text-ink-2 ring-line-strong hover:text-ink")}
              >
                {translate(chip.label)}
              </button>
            ))}
          </div>
        </div>
        {filtered.length ? (
          <ul className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {filtered.map((card) => (
              <ProductCard key={card.key} model={card} listId={list.id} />
            ))}
          </ul>
        ) : (
          <EmptyState icon={query ? Search : Heart} title={translate(query ? "Nada encontrado" : "Nenhum item aqui ainda")} className="mt-4" action={<Link className={buttonClass({ variant: "primary" })} to={createProductPath}>{translate("Criar um produto")}</Link>}>
            {translate(query ? `Não encontramos “${query}”. Crie um produto seu com esse nome.` : "Adicione produtos do catálogo para montar sua lista.")}
          </EmptyState>
        )}
      </div>

      <aside aria-labelledby="sua-lista" className="hidden lg:block">
        <Card className="sticky top-10 p-4">
          <h2 id="sua-lista" className="flex items-center gap-2 text-lg font-semibold">
            <ShoppingBasket aria-hidden className="size-5 text-brand" />{translate(" Sua lista")}</h2>
          <p className="text-sm text-ink-3">{translate(pluralize(count, "item", "itens"))}</p>
          <ul className="mt-3 max-h-[55vh] space-y-3 overflow-y-auto pr-1">
            {list.items.map((item) => (
              <li key={item.id} className="border-b border-line pb-3 last:border-0">
                <div className="flex items-start gap-3">
                  <ProductImage image={item.image} category={item.category} name={item.product_name} className="size-10 shrink-0" />
                  <Link to={`/produtos/${item.product_id}`} className="min-w-0 flex-1 break-words text-sm leading-snug font-semibold hover:underline">{item.product_name}</Link>
                  <Link to={`/produtos/${item.product_id}`} aria-label={translate(`Editar ${item.product_name} na sua lista`)} className="shrink-0 rounded-lg p-1.5 text-ink-3 hover:bg-surface-2"><Pencil aria-hidden className="size-4" /></Link>
                </div>
                <ItemControls listId={list.id} item={item} compact />
              </li>
            ))}
            {!count ? <li className="text-sm text-ink-3">{translate("Sua lista está vazia.")}</li> : null}
          </ul>
          <Link to={marketsPath} aria-disabled={!count} className={buttonClass({ variant: "primary", className: cn("mt-4 w-full", !count && "pointer-events-none opacity-50") })}>{translate("Escolher mercados ")}<ArrowRight aria-hidden className="size-4" />
          </Link>
        </Card>
      </aside>

      {count ? <div aria-hidden className="h-20 lg:hidden" /> : null}
      {count ? (
        <div className="fixed inset-x-4 bottom-24 z-30 lg:hidden">
          <Link to={marketsPath} className="flex items-center justify-between rounded-2xl bg-brand px-5 py-3.5 text-on-brand shadow-lift">
            <span className="flex items-center gap-2 font-semibold">
              <ShoppingBasket aria-hidden className="size-5" /> {translate(pluralize(count, "item", "itens"))}{translate(" na lista")}</span>
            <span className="flex items-center gap-1 text-sm font-semibold">{translate("Continuar ")}<ArrowRight aria-hidden className="size-4" />
            </span>
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export function RemoveButton({ onClick, label }: { onClick: () => void; label: string }) {
  useLocale();
  return (
    <Button variant="ghost" size="icon-sm" onClick={onClick} aria-label={translate(label)}>
      <Trash2 aria-hidden className="size-4" />
    </Button>
  );
}
