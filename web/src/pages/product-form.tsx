import { translate, useLocale } from "@/lib/i18n";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { BellRing, ImagePlus, Link2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { z } from "zod";
import { api, errorMessage, type Schemas, unwrap, uploadImage } from "@/api/client";
import { keys, useAlerts, useCatalog, useDeleteAlert, useDeleteProduct, useProducts, useSaveProduct, useSetAlert } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { ProductImage } from "@/components/domain";
import { Button, Card, Dialog, ErrorState, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow } from "@/components/ui";
import { ago, money, parseMoneyInput } from "@/lib/format";
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
    package_unit: z.enum(["g", "kg", "ml", "l", "un", "m"]).optional(),
    preferred_brand: z.string().max(80).optional(),
    strict_brand: z.boolean(),
    size_tolerance_pct: z.coerce.number().min(0).max(100),
    search_terms: z.string().optional(),
    required_words: z.string().optional(),
    excluded_words: z.string().optional(),
    substitute_brands: z.string().optional(),
    is_favorite: z.boolean(),
    compare_per_metre: z.boolean(),
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
    required_words: (spec.required ?? []).map((group) => group.join(" | ")).join(", "),
    excluded_words: (spec.excluded ?? []).join(", "),
    substitute_brands: (subs.brands ?? []).join(", "),
    is_favorite: product?.is_favorite ?? false,
    compare_per_metre: (product?.match_spec ?? {}).comparison_unit === "m",
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
      required: splitList(values.required_words ?? "").map((group) => group.split("|").map((word) => word.trim()).filter(Boolean)),
      excluded: splitList(values.excluded_words ?? ""),
      sold_by: values.sold_by,
      comparison_unit: values.sold_by === "package" && values.package_unit === "m" && values.compare_per_metre ? "m" : null,
    },
    is_favorite: values.is_favorite,
  };
}

function PriceAlertCard({ product }: { product: Schemas["ProductOut"] }) {
  useLocale();
  const alerts = useAlerts();
  const setAlert = useSetAlert();
  const remove = useDeleteAlert();
  const current = alerts.data?.find((a) => a.product_id === product.id);
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? (current ? String(current.target_price).replace(".", ",") : "");
  const amount = parseMoneyInput(value);
  const unit = translate(product.sold_by === "weight" ? "kg" : product.sold_by === "unit" ? "unidade" : "embalagem");
  const save = (enabled = current?.enabled ?? true) =>
    amount !== null && setAlert.mutate({ productId: product.id, body: { target_price: String(amount), enabled } }, { onSuccess: () => { setDraft(null); toast.success(translate("Alerta salvo")); } });
  return (
    <Card as="section" aria-labelledby="alerta-preco" className="mt-5 space-y-4 p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-content-center rounded-full bg-accent-soft text-accent-ink">
          <BellRing aria-hidden className="size-5" />
        </span>
        <div>
          <h2 id="alerta-preco" className="text-lg font-semibold">{translate("Alerta de preço")}</h2>
          <p className="text-sm text-ink-2">{translate("Avisamos em “Avisos” quando uma busca encontrar este produto por até este valor por ")}{translate(unit)}{translate(" em uma das suas lojas. Promoções contam; preço de clube só se você ativou o clube no perfil.")}</p>
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <Field label={translate(`Preço-alvo por ${unit} (R$)`)} htmlFor="alert_target" className="w-44">
          <Input id="alert_target" inputMode="decimal" placeholder={translate("0,00")} value={value} onChange={(e) => setDraft(e.target.value)} />
        </Field>
        <Button disabled={amount === null} loading={setAlert.isPending} onClick={() => save()}>
          {translate(current ? "Atualizar alerta" : "Criar alerta")}
        </Button>
        {current ? (
          <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate(product.id, { onSuccess: () => { setDraft(null); toast.success(translate("Alerta removido")); } })}>{translate("Remover")}</Button>
        ) : null}
      </div>
      {current ? (
        <>
          <SwitchRow id="alert_enabled" label={translate("Alerta ativo")} description={translate("Pause sem perder o preço-alvo.")} checked={current.enabled} onCheckedChange={(v) => save(v)} />
          <p className="text-sm text-ink-2">
            {translate(current.best_price ? `Melhor preço atual: ${money(current.best_price)} por ${unit} em ${current.best_store} (${ago(current.best_observed_at)}).` : "Ainda sem preço atual para comparar.")}
            {translate(current.last_triggered_at ? ` Último aviso ${ago(current.last_triggered_at)}.` : "")}
          </p>
        </>
      ) : null}
    </Card>
  );
}

export function ProductFormPage() {
  useLocale();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const isNew = !id;
  const navigate = useNavigate();
  const client = useQueryClient();
  const products = useProducts();
  const catalog = useCatalog();
  const save = useSaveProduct();
  const remove = useDeleteProduct();
  const product = products.data?.find((p) => p.id === id);
  const form = useForm<FormValues>({ resolver: zodResolver(schema) as never, defaultValues: toForm() });
  const soldBy = useWatch({ control: form.control, name: "sold_by" });
  const strictBrand = useWatch({ control: form.control, name: "strict_brand" });
  const packageUnit = useWatch({ control: form.control, name: "package_unit" });
  const comparePerMetre = useWatch({ control: form.control, name: "compare_per_metre" });
  const favorite = useWatch({ control: form.control, name: "is_favorite" });
  const [imageUrl, setImageUrl] = useState("");
  const [imageBusy, setImageBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (product) form.reset(toForm(product));
  }, [product, form]);

  if (!isNew && products.isLoading) return <LoadingBlock label={translate("Carregando produto")} />;
  if (!isNew && !product) return <ErrorState error={translate("Produto não encontrado.")} />;

  const e = form.formState.errors;
  const categories = catalog.data?.categories ?? ["Mercearia"];

  const submit = form.handleSubmit(async (values) => {
    try {
      await save.mutateAsync({ id, body: toBody(values, product) });
      toast.success(translate(isNew ? "Produto criado" : "Produto atualizado"));
      if (isNew) navigate(searchParams.get("flow") === "price-check" ? "/lista?flow=price-check" : "/lista", { replace: true });
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
      toast.success(translate("Imagem atualizada"));
    } catch (error) {
      toast.error(translate(errorMessage(error)));
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
      toast.success(translate("Imagem importada"));
    } catch (error) {
      toast.error(translate(errorMessage(error)));
    } finally {
      setImageBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={isNew ? translate("Novo produto") : <span>{product?.name ?? translate("Produto")}</span>} description={translate("Suas alterações são privadas, inclusive em produtos do catálogo. As regras abaixo decidem quais anúncios dos mercados são equivalentes.")} />
      {isNew ? <Card className="mb-5 space-y-3 p-5">
        <h2 className="font-semibold">{translate("Comece com um modelo")}</h2>
        <Button variant="secondary" onClick={() => form.reset({ ...toForm(), name: "Papel higiênico folha dupla", category: categories.includes("Higiene") ? "Higiene" : categories[0]!, package_quantity: "120", package_unit: "m", compare_per_metre: true, search_terms: "papel higiênico folha dupla, papel higienico", required_words: "papel higienico | toilet paper, folha dupla | folhas duplas | fd | 2 folhas | double ply | 2 ply", excluded_words: "folha simples, folha tripla, papel toalha, guardanapo" })}>{translate("Papel higiênico folha dupla")}</Button>
        <p className="text-sm text-ink-3">{translate("O modelo aceita qualquer marca e tamanho, exige folha dupla e compara pelo preço por metro. Os termos de busca devem seguir o idioma dos mercados.")}</p>
      </Card> : null}
      <form onSubmit={submit} noValidate className="space-y-5">
        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">{translate("O que é")}</h2>
          <Field label={translate("Nome")} htmlFor="name" error={translate(e.name?.message)}>
            <Input id="name" aria-invalid={Boolean(e.name)} {...form.register("name")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={translate("Categoria")} htmlFor="category" error={translate(e.category?.message)}>
              <Select id="category" {...form.register("category")}>
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </Field>
            <Field label={translate("Como é vendido")} htmlFor="sold_by">
              <Select id="sold_by" {...form.register("sold_by")}>
                {Object.entries(SOLD_BY).map(([value, label]) => (
                  <option key={value} value={value}>
                    {translate(label)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {soldBy === "package" ? (
            <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
              <Field label={translate(packageUnit === "m" && comparePerMetre ? "Metros que deseja comprar" : "Tamanho da embalagem")} htmlFor="package_quantity" error={translate(e.package_quantity?.message)} hint={translate(packageUnit === "m" && comparePerMetre ? "Ex.: 120 m. Na lista, o custo considera pacotes inteiros." : "Ex.: 1 kg, 400 g, 30 un")}>
                <Input id="package_quantity" inputMode="decimal" aria-invalid={Boolean(e.package_quantity)} {...form.register("package_quantity")} />
              </Field>
              <Field label={translate("Unidade")} htmlFor="package_unit" error={translate(e.package_unit?.message)}>
                <Select id="package_unit" {...form.register("package_unit")}>
                  <option value="g">{translate("g")}</option>
                  <option value="kg">{translate("kg")}</option>
                  <option value="ml">{translate("ml")}</option>
                  <option value="l">{translate("L")}</option>
                  <option value="un">{translate("unidades")}</option>
                  <option value="m">{translate("m (metros)")}</option>
                </Select>
              </Field>
            </div>
          ) : (
            <InlineAlert tone="info">{translate(soldBy === "weight" ? "Comparado pelo preço por kg; na lista você informa quantos kg quer." : "Comparado pelo preço de cada unidade.")}</InlineAlert>
          )}
        </Card>

        {soldBy === "package" && packageUnit === "m" ? <Card className="space-y-3 p-5">
          <SwitchRow id="compare_per_metre" label={translate("Comparar qualquer tamanho pelo preço por metro")} checked={comparePerMetre} onCheckedChange={(v) => form.setValue("compare_per_metre", v)} />
          <p className="text-sm text-ink-3">{translate("Informe acima a quantidade de metros que deseja comprar (ex.: 120 m). Um pacote com 4 rolos de 30 m contém 120 m; um com 12 rolos de 30 m contém 360 m. O custo da lista considera pacotes inteiros. Anúncios sem comprimento total identificável ficam fora da comparação.")}</p>
        </Card> : null}
        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">{translate("Marca e substituições")}</h2>
          <Field label={translate("Marca preferida")} htmlFor="preferred_brand" hint={translate("Opcional. Deixe em branco para aceitar qualquer marca.")}>
            <Input id="preferred_brand" {...form.register("preferred_brand")} />
          </Field>
          <SwitchRow id="strict_brand" label={translate("Aceitar somente esta marca")} description={translate("Se desligado, a marca preferida só ajuda a ordenar os resultados.")} checked={strictBrand} onCheckedChange={(v) => form.setValue("strict_brand", v)} />
          <Field label={translate("Marcas aceitas como substitutas")} htmlFor="substitute_brands" hint={translate("Separadas por vírgula.")}>
            <Input id="substitute_brands" {...form.register("substitute_brands")} />
          </Field>
          {soldBy === "package" && !(packageUnit === "m" && comparePerMetre) ? (
            <Field label={translate("Tolerância de tamanho (%)")} htmlFor="size_tolerance_pct" hint={translate("0% exige o tamanho exato. 25% aceita 300–500 g para 400 g, calculando pelo preço por unidade.")}>
              <Input id="size_tolerance_pct" type="number" min={0} max={100} step={5} {...form.register("size_tolerance_pct")} />
            </Field>
          ) : null}
        </Card>

        <Card className="space-y-4 p-5">
          <h2 className="text-lg font-semibold">{translate("Como encontrar nos mercados")}</h2>
          <Field label={translate("Termos de busca")} htmlFor="search_terms" hint={translate("Separados por vírgula, do mais específico ao mais geral.")}>
            <Input id="search_terms" {...form.register("search_terms")} />
          </Field>
          <Field label={translate("Palavras obrigatórias")} htmlFor="required_words" hint={translate("Separe grupos por vírgula; todos precisam aparecer. Use | para alternativas (ex.: ovo | ovos, branco). O primeiro grupo é o produto principal.")}>
            <Input id="required_words" {...form.register("required_words")} />
          </Field>
          <Field label={translate("Palavras que excluem")} htmlFor="excluded_words" hint={translate("Anúncios com qualquer uma delas são descartados (ex.: integral, orgânico).")}>
            <Input id="excluded_words" {...form.register("excluded_words")} />
          </Field>
          <SwitchRow id="is_favorite" label={translate("Favorito")} checked={favorite} onCheckedChange={(v) => form.setValue("is_favorite", v)} />
        </Card>

        <div className="flex flex-wrap gap-2">
          <Button type="submit" loading={save.isPending}>
            {translate(isNew ? "Criar produto" : "Salvar alterações")}
          </Button>
          <Button variant="ghost" onClick={() => navigate(-1)}>{translate("Voltar")}</Button>
        </div>
      </form>

      {!isNew && product ? (
        <>
          <Card className="mt-5 space-y-4 p-5">
            <h2 className="text-lg font-semibold">{translate("Imagem")}</h2>
            <div className="flex flex-wrap items-start gap-5">
              <ProductImage image={product.image} category={product.category} name={product.name} className="size-32" />
              <div className="min-w-0 flex-1 basis-60 space-y-3">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-semibold ring-1 ring-line-strong hover:bg-surface-2">
                  <ImagePlus aria-hidden className="size-4" />{translate(" Enviar foto")}<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" disabled={imageBusy} onChange={(ev) => ev.target.files?.[0] && void onUpload(ev.target.files[0])} />
                </label>
                <div className="flex gap-2">
                  <Input aria-label={translate("Endereço https da imagem")} placeholder={translate("https://… (imagem pública)")} value={imageUrl} onChange={(ev) => setImageUrl(ev.target.value)} />
                  <Button variant="secondary" onClick={() => void onImportUrl()} loading={imageBusy} disabled={!imageUrl}>
                    <Link2 aria-hidden className="size-4" />{translate(" Importar")}</Button>
                </div>
                <p className="text-xs text-ink-3">{translate("JPEG, PNG ou WebP até 5 MB. A imagem é validada, redimensionada e guardada no servidor; endereços privados ou locais são recusados.")}</p>
              </div>
            </div>
          </Card>
          <PriceAlertCard product={product} />
          <Card className="mt-5 flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <h2 className="text-lg font-semibold">{translate("Remover produto")}</h2>
              <p className="text-sm text-ink-3">{translate("Tira o produto das listas e apaga o histórico de preços dele.")}</p>
            </div>
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>
              <Trash2 aria-hidden className="size-4" />{translate(" Remover")}</Button>
          </Card>
          <Dialog
            open={confirmDelete}
            onOpenChange={setConfirmDelete}
            title={translate("Remover produto?")}
            description={translate("O produto sai de todas as listas e o histórico de preços dele é apagado. Para só pausar, desative-o na lista.")}
            footer={
              <>
                <Button variant="ghost" onClick={() => setConfirmDelete(false)}>{translate("Cancelar")}</Button>
                <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate(product.id, { onSuccess: () => navigate("/lista", { replace: true }) })}>{translate("Remover definitivamente")}</Button>
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
