import { ArrowRight, Heart, PackagePlus, Pencil, Plus, Search, ShoppingBasket, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import type { Schemas } from "@/api/client";
import { useAddToList, useCatalog, useDefaultList, useProducts, useRemoveListItem, useUpdateListItem } from "@/api/hooks";
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
  item?: Schemas["ListItemOut"];
};

const STEP: Record<string, number> = { kg: 0.5, g: 100, l: 1, ml: 100, un: 1, pct: 1 };

function normalize(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function ItemControls({ listId, item, compact }: { listId: string; item: Schemas["ListItemOut"]; compact?: boolean }) {
  const update = useUpdateListItem();
  const remove = useRemoveListItem();
  const quantity = Number(item.quantity);
  const step = STEP[item.unit] ?? 1;
  return (
    <div className={cn("flex flex-wrap items-center gap-2", compact && "justify-end")}>
      <Stepper
        label={`quantidade de ${item.product_name}`}
        value={quantity}
        step={step}
        min={0}
        onChange={(value) => {
          if (value <= 0) remove.mutate({ listId, itemId: item.id });
          else update.mutate({ listId, itemId: item.id, body: { quantity: String(value) } });
        }}
      />
      {item.allowed_units.length > 1 ? (
        <Select aria-label={`Unidade de ${item.product_name}`} className="h-9 w-auto rounded-full py-0 pr-9 pl-3 text-sm" value={item.unit} onChange={(e) => update.mutate({ listId, itemId: item.id, body: { unit: e.target.value as Schemas["Unit"] } })}>
          {item.allowed_units.map((unit) => (
            <option key={unit} value={unit}>
              {UNIT_OPTIONS[unit] ?? unit}
            </option>
          ))}
        </Select>
      ) : (
        <span className="text-sm text-ink-3">{UNIT_OPTIONS[item.unit] ?? item.unit}</span>
      )}
    </div>
  );
}

function ProductCard({ model, listId }: { model: CardModel; listId: string }) {
  const add = useAddToList();
  const inList = Boolean(model.item);
  return (
    <li>
      <Card className={cn("flex h-full flex-col gap-3 p-3 transition-shadow hover:shadow-lift", inList && "ring-2 ring-brand/40")}>
        <div className="relative">
          <ProductImage image={model.image} category={model.category} name={model.name} />
          {model.custom ? <span className="absolute top-2 left-2 rounded-full bg-surface/90 px-2 py-0.5 text-[11px] font-bold text-ink-2">Meu produto</span> : null}
          {model.productId && model.custom ? (
            <Link to={`/produtos/${model.productId}`} className="absolute top-2 right-2 grid size-8 place-content-center rounded-full bg-surface/90 text-ink-2 hover:text-ink" aria-label={`Editar ${model.name}`}>
              <Pencil aria-hidden className="size-4" />
            </Link>
          ) : null}
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
            aria-label={`Adicionar ${model.name}`}
            onClick={() => add.mutate({ listId, body: model.catalogItemId ? { catalog_item_id: model.catalogItemId } : { product_id: model.productId } })}
          >
            <Plus aria-hidden className="size-4" /> Adicionar
          </Button>
        )}
      </Card>
    </li>
  );
}

export function ListPage() {
  const catalog = useCatalog();
  const products = useProducts();
  const { list, isLoading: listLoading, error: listError, refetch } = useDefaultList();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("todos");

  const cards = useMemo<CardModel[]>(() => {
    const itemsByProduct = new Map((list?.items ?? []).map((item) => [item.product_id, item]));
    const fromCatalog: CardModel[] = (catalog.data?.items ?? []).map((item) => ({
      key: `c-${item.id}`,
      name: item.name,
      category: item.category,
      image: item.image,
      pkg: packageLabel(item.package_quantity, item.package_unit, item.sold_by),
      catalogItemId: item.id,
      productId: item.my_product_id ?? undefined,
      item: item.my_product_id ? itemsByProduct.get(item.my_product_id) : undefined,
    }));
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
        <PageHeader title="Monte sua lista" />
        <LoadingBlock label="Carregando catálogo" rows={4} />
      </>
    );
  }
  if (catalog.error || listError || !list) {
    return (
      <>
        <PageHeader title="Monte sua lista" />
        <ErrorState error="Não foi possível carregar o catálogo ou a lista." onRetry={() => void refetch()} />
      </>
    );
  }

  const count = list.item_count;
  return (
    <div className="lg:grid lg:grid-cols-[1fr_20rem] lg:gap-8">
      <div className="min-w-0">
        <PageHeader
          title="Monte sua lista"
          description="Escolha no catálogo ou crie seus próprios produtos. Quantidade da lista e tamanho da embalagem são coisas diferentes: 2 pacotes de 1 kg custam duas vezes o pacote."
          actions={
            <Link to="/produtos/novo" className={buttonClass({ variant: "secondary" })}>
              <PackagePlus aria-hidden className="size-4" /> Criar produto
            </Link>
          }
        />
        <div className="sticky top-14 z-20 -mx-4 space-y-3 bg-canvas/95 px-4 pt-1 pb-3 backdrop-blur lg:top-0 lg:mx-0 lg:px-0">
          <div className="relative">
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-ink-3" />
            <Input type="search" placeholder="Buscar produto" aria-label="Buscar produto" value={query} onChange={(e) => setQuery(e.target.value)} className="rounded-full pl-10" />
          </div>
          <div className="scrollbar-none -mx-4 flex gap-2 overflow-x-auto px-4 lg:mx-0 lg:px-0" role="group" aria-label="Filtrar por categoria">
            {[{ id: "todos", label: "Todos" }, { id: "na-lista", label: `Na lista (${count})` }, ...categories.map((c) => ({ id: c, label: c }))].map((chip) => (
              <button
                key={chip.id}
                type="button"
                onClick={() => setCategory(chip.id)}
                aria-pressed={category === chip.id}
                className={cn("h-9 shrink-0 rounded-full px-4 text-sm font-semibold ring-1 transition-colors", category === chip.id ? "bg-ink text-canvas ring-ink" : "bg-surface text-ink-2 ring-line-strong hover:text-ink")}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
        {filtered.length ? (
          <ul className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {filtered.map((card) => (
              <ProductCard key={card.key} model={card} listId={list.id} />
            ))}
          </ul>
        ) : (
          <EmptyState icon={query ? Search : Heart} title={query ? "Nada encontrado" : "Nenhum item aqui ainda"} className="mt-4" action={<Link className={buttonClass({ variant: "primary" })} to="/produtos/novo">Criar um produto</Link>}>
            {query ? `Não encontramos “${query}”. Crie um produto seu com esse nome.` : "Adicione produtos do catálogo para montar sua lista."}
          </EmptyState>
        )}
      </div>

      <aside aria-labelledby="sua-lista" className="hidden lg:block">
        <Card className="sticky top-10 p-4">
          <h2 id="sua-lista" className="flex items-center gap-2 text-lg font-semibold">
            <ShoppingBasket aria-hidden className="size-5 text-brand" /> Sua lista
          </h2>
          <p className="text-sm text-ink-3">{pluralize(count, "item", "itens")}</p>
          <ul className="mt-3 max-h-[55vh] space-y-3 overflow-y-auto pr-1">
            {list.items.map((item) => (
              <li key={item.id} className="flex items-center gap-3">
                <ProductImage image={item.image} category={item.category} name={item.product_name} className="size-12 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">{item.product_name}</p>
                  <ItemControls listId={list.id} item={item} compact />
                </div>
              </li>
            ))}
            {!count ? <li className="text-sm text-ink-3">Sua lista está vazia.</li> : null}
          </ul>
          <Link to="/mercados" aria-disabled={!count} className={buttonClass({ variant: "primary", className: cn("mt-4 w-full", !count && "pointer-events-none opacity-50") })}>
            Escolher mercados <ArrowRight aria-hidden className="size-4" />
          </Link>
        </Card>
      </aside>

      {count ? <div aria-hidden className="h-20 lg:hidden" /> : null}
      {count ? (
        <div className="fixed inset-x-4 bottom-24 z-30 lg:hidden">
          <Link to="/mercados" className="flex items-center justify-between rounded-2xl bg-brand px-5 py-3.5 text-on-brand shadow-lift">
            <span className="flex items-center gap-2 font-semibold">
              <ShoppingBasket aria-hidden className="size-5" /> {pluralize(count, "item", "itens")} na lista
            </span>
            <span className="flex items-center gap-1 text-sm font-semibold">
              Continuar <ArrowRight aria-hidden className="size-4" />
            </span>
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export function RemoveButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <Button variant="ghost" size="icon-sm" onClick={onClick} aria-label={label}>
      <Trash2 aria-hidden className="size-4" />
    </Button>
  );
}
