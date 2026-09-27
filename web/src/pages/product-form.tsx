import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Link2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { z } from "zod";
import { api, errorMessage, type Schemas, unwrap, uploadImage } from "@/api/client";
import { keys, useCatalog, useDeleteProduct, useProducts, useSaveProduct } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { ProductImage } from "@/components/domain";
import { Button, Card, Dialog, ErrorState, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow } from "@/components/ui";
import { SOLD_BY } from "@/lib/labels";

const splitList = (value: string) =>
  value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

const schema = z
  .object({
    name: z.string().trim().min(2, "Informe o nome do produto.").max(120),
    category: z.string().min(2, "Escolha uma categoria."),
    sold_by: z.enum(["package", "weight", "unit"]),
    package_quantity: z.string().optional(),
    package_unit: z.enum(["g", "kg", "ml", "l", "un"]).optional(),
    preferred_brand: z.string().max(80).optional(),
    strict_brand: z.boolean(),
    size_tolerance_pct: z.coerce.number().min(0).max(100),
    search_terms: z.string().optional(),
    required_words: z.string().optional(),
    excluded_words: z.string().optional(),
    substitute_brands: z.string().optional(),
    is_favorite: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.sold_by === "package") {
      const qty = Number((v.package_quantity ?? "").replace(",", "."));
      if (!Number.isFinite(qty) || qty <= 0) ctx.addIssue({ code: "custom", path: ["package_quantity"], message: "Informe o tamanho (ex.: 1, 400, 30)." });
      if (!v.package_unit) ctx.addIssue({ code: "custom", path: ["package_unit"], message: "Escolha a unidade." });
    }
  });

type FormValues = z.infer<typeof schema>;

function toForm(product?: Schemas["ProductOut"]): FormValues {
  const spec = (product?.match_spec ?? {}) as { search_terms?: string[]; required?: string[][]; excluded?: string[] };
  const subs = (product?.substitutions ?? {}) as { brands?: string[] };
  return {
    name: product?.name ?? "",
    category: product?.category ?? "Mercearia",
    sold_by: (product?.sold_by as FormValues["sold_by"]) ?? "package",
    package_quantity: product?.package_quantity ? String(Number(product.package_quantity)) : "",
    package_unit: (product?.package_unit as FormValues["package_unit"]) ?? "g",
    preferred_brand: product?.preferred_brand ?? "",
    strict_brand: product?.strict_brand ?? false,
    size_tolerance_pct: Number(product?.size_tolerance_pct ?? 0),
    search_terms: (spec.search_terms ?? []).join(", "),
    required_words: (spec.required ?? []).map((group) => group[0]).join(", "),
    excluded_words: (spec.excluded ?? []).join(", "),
    substitute_brands: (subs.brands ?? []).join(", "),
    is_favorite: product?.is_favorite ?? false,
  };
}

function toBody(values: FormValues, original?: Schemas["ProductOut"]): Schemas["ProductIn"] {
  const originalSpec = (original?.match_spec ?? {}) as Record<string, unknown>;
  const terms = splitList(values.search_terms ?? "");
  return {
    name: values.name,
    category: values.category,
    sold_by: values.sold_by,
    package_quantity: values.sold_by === "package" ? String(Number((values.package_quantity ?? "").replace(",", "."))) : null,
    package_unit: values.sold_by === "package" ? (values.package_unit ?? null) : null,
    preferred_brand: values.preferred_brand?.trim() || null,
    strict_brand: values.strict_brand,
    size_tolerance_pct: String(values.size_tolerance_pct),
    substitutions: { brands: splitList(values.substitute_brands ?? "") },
    match_spec: {
      ...originalSpec,
      search_terms: terms.length ? terms : [values.name],
      required: splitList(values.required_words ?? "").map((word) => [word]),
      excluded: splitList(values.excluded_words ?? ""),
      sold_by: values.sold_by,
    },
    is_favorite: values.is_favorite,
  };
}

export function ProductFormPage() {
  const { id } = useParams();
  const isNew = !id;
  const navigate = useNavigate();
  const client = useQueryClient();
  const products = useProducts();
  const catalog = useCatalog();
  const save = useSaveProduct();
  const remove = useDeleteProduct();
  const product = products.data?.find((p) => p.id === id);
  const form = useForm<FormValues>({ resolver: zodResolver(schema) as never, defaultValues: toForm() });
  const [imageUrl, setImageUrl] = useState("");
  const [imageBusy, setImageBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (product) form.reset(toForm(product));
  }, [product, form]);

  if (!isNew && products.isLoading) return <LoadingBlock label="Carregando produto" />;
  if (!isNew && !product) return <ErrorState error="Produto não encontrado." />;

  const soldBy = form.watch("sold_by");
  const e = form.formState.errors;
  const categories = catalog.data?.categories ?? ["Mercearia"];

  const submit = form.handleSubmit(async (values) => {
    try {
      const saved = await save.mutateAsync({ id, body: toBody(values, product) });
      toast.success(isNew ? "Produto criado" : "Produto atualizado");
      if (isNew) navigate(`/produtos/${saved.id}`, { replace: true });
    } catch {
      /* toast shown by the mutation */
    }
  });

  async function onUpload(file: File) {
    if (!id) return;
    setImageBusy(true);
    try {
      await uploadImage(`/api/v1/products/${id}/image`, file);
      await client.invalidateQueries({ queryKey: keys.products });
      await client.invalidateQueries({ queryKey: keys.lists });
      toast.success("Imagem atualizada");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setImageBusy(false);
    }
  }

  async function onImportUrl() {
    if (!id || !imageUrl) return;
    setImageBusy(true);
    try {
      await unwrap(api.POST("/api/v1/products/{product_id}/image-url", { params: { path: { product_id: id } }, body: { url: imageUrl } }));
      setImageUrl("");
      await client.invalidateQueries({ queryKey: keys.products });
      toast.success("Imagem importada");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setImageBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={isNew ? "Novo produto" : product?.name ?? "Produto"} description="Produtos criados por você são privados. As regras abaixo decidem, de forma explicável, quais anúncios dos mercados são equivalentes." />
      <form onSubmit={submit} noValidate className="space-y-5">
        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">O que é</h2>
          <Field label="Nome" htmlFor="name" error={e.name?.message}>
            <Input id="name" aria-invalid={Boolean(e.name)} {...form.register("name")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Categoria" htmlFor="category" error={e.category?.message}>
              <Select id="category" {...form.register("category")}>
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </Field>
            <Field label="Como é vendido" htmlFor="sold_by">
              <Select id="sold_by" {...form.register("sold_by")}>
                {Object.entries(SOLD_BY).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {soldBy === "package" ? (
            <div className="grid grid-cols-[1fr_8rem] gap-3">
              <Field label="Tamanho da embalagem" htmlFor="package_quantity" error={e.package_quantity?.message} hint="Ex.: 1 kg, 400 g, 30 un">
                <Input id="package_quantity" inputMode="decimal" aria-invalid={Boolean(e.package_quantity)} {...form.register("package_quantity")} />
              </Field>
              <Field label="Unidade" htmlFor="package_unit" error={e.package_unit?.message}>
                <Select id="package_unit" {...form.register("package_unit")}>
                  <option value="g">g</option>
                  <option value="kg">kg</option>
                  <option value="ml">ml</option>
                  <option value="l">L</option>
                  <option value="un">unidades</option>
                </Select>
              </Field>
            </div>
          ) : (
            <InlineAlert tone="info">{soldBy === "weight" ? "Comparado pelo preço por kg; na lista você informa quantos kg quer." : "Comparado pelo preço de cada unidade."}</InlineAlert>
          )}
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Marca e substituições</h2>
          <Field label="Marca preferida" htmlFor="preferred_brand" hint="Opcional. Deixe em branco para aceitar qualquer marca.">
            <Input id="preferred_brand" {...form.register("preferred_brand")} />
          </Field>
          <SwitchRow id="strict_brand" label="Aceitar somente esta marca" description="Se desligado, a marca preferida só ajuda a ordenar os resultados." checked={form.watch("strict_brand")} onCheckedChange={(v) => form.setValue("strict_brand", v)} />
          <Field label="Marcas aceitas como substitutas" htmlFor="substitute_brands" hint="Separadas por vírgula.">
            <Input id="substitute_brands" {...form.register("substitute_brands")} />
          </Field>
          {soldBy === "package" ? (
            <Field label="Tolerância de tamanho (%)" htmlFor="size_tolerance_pct" hint="0% exige o tamanho exato. 25% aceita 300–500 g para 400 g, calculando pelo preço por unidade.">
              <Input id="size_tolerance_pct" type="number" min={0} max={100} step={5} {...form.register("size_tolerance_pct")} />
            </Field>
          ) : null}
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">Como encontrar nos mercados</h2>
          <Field label="Termos de busca" htmlFor="search_terms" hint="Separados por vírgula, do mais específico ao mais geral.">
            <Input id="search_terms" {...form.register("search_terms")} />
          </Field>
          <Field label="Palavras obrigatórias" htmlFor="required_words" hint="Todas precisam aparecer no nome do anúncio. A primeira deve ser o produto principal.">
            <Input id="required_words" {...form.register("required_words")} />
          </Field>
          <Field label="Palavras que excluem" htmlFor="excluded_words" hint="Anúncios com qualquer uma delas são descartados (ex.: integral, orgânico).">
            <Input id="excluded_words" {...form.register("excluded_words")} />
          </Field>
          <SwitchRow id="is_favorite" label="Favorito" checked={form.watch("is_favorite")} onCheckedChange={(v) => form.setValue("is_favorite", v)} />
        </Card>

        <div className="flex flex-wrap gap-2">
          <Button type="submit" loading={save.isPending}>
            {isNew ? "Criar produto" : "Salvar alterações"}
          </Button>
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Voltar
          </Button>
        </div>
      </form>

      {!isNew && product ? (
        <>
          <Card className="mt-5 space-y-4 p-5">
            <h2 className="text-lg font-semibold">Imagem</h2>
            <div className="flex flex-wrap items-start gap-5">
              <ProductImage image={product.image} category={product.category} name={product.name} className="size-32" />
              <div className="min-w-0 flex-1 space-y-3">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-semibold ring-1 ring-line-strong hover:bg-surface-2">
                  <ImagePlus aria-hidden className="size-4" /> Enviar foto
                  <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" disabled={imageBusy} onChange={(ev) => ev.target.files?.[0] && void onUpload(ev.target.files[0])} />
                </label>
                <div className="flex gap-2">
                  <Input aria-label="Endereço https da imagem" placeholder="https://… (imagem pública)" value={imageUrl} onChange={(ev) => setImageUrl(ev.target.value)} />
                  <Button variant="secondary" onClick={() => void onImportUrl()} loading={imageBusy} disabled={!imageUrl}>
                    <Link2 aria-hidden className="size-4" /> Importar
                  </Button>
                </div>
                <p className="text-xs text-ink-3">JPEG, PNG ou WebP até 5 MB. A imagem é validada, redimensionada e guardada no servidor; endereços privados ou locais são recusados.</p>
              </div>
            </div>
          </Card>
          <Card className="mt-5 flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <h2 className="text-lg font-semibold">Remover produto</h2>
              <p className="text-sm text-ink-3">Tira o produto das listas e apaga o histórico de preços dele.</p>
            </div>
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>
              <Trash2 aria-hidden className="size-4" /> Remover
            </Button>
          </Card>
          <Dialog
            open={confirmDelete}
            onOpenChange={setConfirmDelete}
            title="Remover produto?"
            description="O produto sai de todas as listas e o histórico de preços dele é apagado. Para só pausar, desative-o na lista."
            footer={
              <>
                <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Cancelar
                </Button>
                <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate(product.id, { onSuccess: () => navigate("/lista", { replace: true }) })}>
                  Remover definitivamente
                </Button>
              </>
            }
          >
            <p className="text-sm">{product.name}</p>
          </Dialog>
        </>
      ) : null}
    </div>
  );
}
