import { translate, useLocale } from "@/lib/i18n";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Car, KeyRound, LocateFixed, LogOut, MapPin, MonitorSmartphone, Save, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errorMessage, type Schemas, unwrap } from "@/api/client";
import { keys, useAddresses, useMarkets, useMe, useMeta, useProfile, useSaveAddress, useSaveVehicle, useUpdateProfile, useVehicles } from "@/api/hooks";
import { PageHeader } from "@/app/shell";
import { ChangePasswordForm, RecoveryCodes } from "@/pages/auth";
import { Badge, Button, Card, Dialog, Field, InlineAlert, Input, LoadingBlock, Select, SwitchRow } from "@/components/ui";
import { ago, formatDateTime, money } from "@/lib/format";

function SectionCard({ id, icon: Icon, title, description, children }: { id: string; icon: typeof Car; title: string; description?: string; children: React.ReactNode }) {
  useLocale();
  return (
    <Card id={id} className="scroll-mt-20 space-y-4 p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-content-center rounded-xl bg-brand-soft text-brand">
          <Icon aria-hidden className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-semibold">{translate(title)}</h2>
          {description ? <p className="text-sm text-ink-3">{translate(description)}</p> : null}
        </div>
      </div>
      {translate(children)}
    </Card>
  );
}

function Preferences() {
  useLocale();
  const profile = useProfile();
  const markets = useMarkets();
  const update = useUpdateProfile();
  const [draftName, setName] = useState<string | null>(null);
  const name = draftName ?? profile.data?.display_name ?? "";
  if (!profile.data) return <LoadingBlock rows={1} />;
  const p = profile.data;
  const clubs = new Set(p.use_club_prices);
  return (
    <SectionCard id="preferencias" icon={SlidersHorizontal} title={translate("Preferências da comparação")}>
      <div className="flex gap-2">
        <Field label={translate("Seu nome")} htmlFor="display_name" className="flex-1">
          <Input id="display_name" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Button variant="secondary" className="mt-7" disabled={!name || name === p.display_name} onClick={() => update.mutate({ display_name: name }, { onSuccess: () => setName(null) })}>{translate("Salvar")}</Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={translate("Preço vale por (dias)")} htmlFor="freshness" hint={translate("Preços mais antigos ficam no histórico, fora da recomendação.")}>
          <Select id="freshness" value={p.freshness_days} onChange={(e) => update.mutate({ freshness_days: Number(e.target.value) })}>
            {[3, 5, 7, 10, 14, 21, 30].map((d) => (
              <option key={d} value={d}>
                {translate(d)}{translate(" dias")}</option>
            ))}
          </Select>
        </Field>
        <Field label={translate("Máximo de lojas por compra")} htmlFor="max_stops" hint={translate("Usado no plano econômico.")}>
          <Select id="max_stops" value={p.max_stops} onChange={(e) => update.mutate({ max_stops: Number(e.target.value) })}>
            <option value={1}>{translate("1 loja")}</option>
            <option value={2}>{translate("até 2 lojas")}</option>
            <option value={3}>{translate("até 3 lojas")}</option>
          </Select>
        </Field>
      </div>
      <SwitchRow id="include_travel" label={translate("Incluir custo de deslocamento")} description={translate("Soma combustível e pedágios de ida e volta ao total de cada loja.")} checked={p.include_travel_cost} onCheckedChange={(v) => update.mutate({ include_travel_cost: v })} />
      <div>
        <p className="text-[15px] font-semibold">{translate("Uso preço de clube/app em:")}</p>
        <p className="mb-2 text-sm text-ink-3">{translate("Marque só onde você tem cadastro no clube. Nos demais, o preço de clube aparece, mas não entra no total.")}</p>
        <div className="flex flex-wrap gap-2">
          {(markets.data ?? []).map((m) => (
            <label key={m.slug} className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-surface-2 px-3 py-1.5 text-sm font-semibold ring-1 ring-line has-checked:bg-brand-soft has-checked:ring-brand/40">
              <input
                type="checkbox"
                className="size-4 accent-[var(--color-brand)]"
                checked={clubs.has(m.slug)}
                onChange={(e) => {
                  const next = new Set(clubs);
                  if (e.target.checked) next.add(m.slug);
                  else next.delete(m.slug);
                  update.mutate({ use_club_prices: [...next] });
                }}
              />
              {m.name}
            </label>
          ))}
        </div>
      </div>
    </SectionCard>
  );
}

const emptyAddress: Schemas["AddressIn"] = { label: "Casa", postal_code: "", street: "", number: "", complement: "", district: "", city: "", state: "SC", latitude: null, longitude: null, is_primary: true };

function AddressSection() {
  useLocale();
  const addresses = useAddresses();
  const meta = useMeta();
  const save = useSaveAddress();
  const client = useQueryClient();
  const current = addresses.data?.[0];
  // Edits live in a draft over the saved address, so fresh server data shows until the user types.
  const [draft, setDraft] = useState<Schemas["AddressIn"] | null>(null);
  const base: Schemas["AddressIn"] = current ? { ...emptyAddress, ...current } : emptyAddress;
  const form = draft ?? base;
  const setForm = (update: (f: Schemas["AddressIn"]) => Schemas["AddressIn"]) => setDraft((d) => update(d ?? base));
  const [locating, setLocating] = useState(false);
  const set = (key: keyof Schemas["AddressIn"]) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));

  function useBrowserLocation() {
    if (!navigator.geolocation) {
      toast.error(translate("Seu navegador não permite obter a localização."));
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setForm((f) => ({ ...f, latitude: position.coords.latitude.toFixed(6), longitude: position.coords.longitude.toFixed(6) }));
        setLocating(false);
        toast.success(translate("Localização obtida. Salve para usar."));
      },
      () => {
        setLocating(false);
        toast.error(translate("Não foi possível obter a localização."));
      },
      { enableHighAccuracy: false, timeout: 15000 },
    );
  }

  async function geocode() {
    if (!current) return;
    try {
      await unwrap(api.POST("/api/v1/me/addresses/{address_id}/geocode", { params: { path: { address_id: current.id } } }));
      await client.invalidateQueries({ queryKey: keys.addresses });
      toast.success(translate("Endereço localizado"));
    } catch (error) {
      toast.error(translate(errorMessage(error)));
    }
  }

  const located = form.latitude !== null && form.latitude !== undefined && form.latitude !== "";
  return (
    <SectionCard id="endereco" icon={MapPin} title={translate("Endereço de casa")} description={translate("Usado só para calcular a distância até as lojas. Fica privado na sua conta e nunca aparece em logs.")}>
      <div className="grid gap-3 sm:grid-cols-[8rem_1fr_6rem]">
        <Field label={translate("CEP")} htmlFor="postal_code">
          <Input id="postal_code" inputMode="numeric" autoComplete="postal-code" value={form.postal_code ?? ""} onChange={set("postal_code")} />
        </Field>
        <Field label={translate("Rua")} htmlFor="street">
          <Input id="street" autoComplete="address-line1" value={form.street ?? ""} onChange={set("street")} />
        </Field>
        <Field label={translate("Número")} htmlFor="number">
          <Input id="number" value={form.number ?? ""} onChange={set("number")} />
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_5rem]">
        <Field label={translate("Bairro")} htmlFor="district">
          <Input id="district" value={form.district ?? ""} onChange={set("district")} />
        </Field>
        <Field label={translate("Cidade")} htmlFor="city">
          <Input id="city" autoComplete="address-level2" value={form.city ?? ""} onChange={set("city")} />
        </Field>
        <Field label={translate("UF")} htmlFor="state">
          <Input id="state" maxLength={2} value={form.state ?? ""} onChange={set("state")} />
        </Field>
      </div>
      <div className="rounded-xl bg-surface-2 p-4 ring-1 ring-line">
        <p className="text-sm font-semibold">{translate("Localização ")}{located ? <Badge tone="brand">{translate("definida")}</Badge> : <Badge tone="warn">{translate("pendente")}</Badge>}</p>
        <p className="mb-3 text-sm text-ink-3">{translate("A distância usa estas coordenadas. Nenhum mapa externo é carregado.")}</p>
        <div className="flex flex-wrap items-end gap-2">
          <Button variant="secondary" size="sm" onClick={useBrowserLocation} loading={locating}>
            <LocateFixed aria-hidden className="size-4" />{translate(" Usar minha localização atual")}</Button>
          {meta.data?.geocoder === "nominatim" && current ? (
            <Button variant="secondary" size="sm" onClick={() => void geocode()}>
              <MapPin aria-hidden className="size-4" />{translate(" Localizar pelo endereço")}</Button>
          ) : null}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <Field label={translate("Latitude")} htmlFor="latitude">
            <Input id="latitude" inputMode="decimal" value={form.latitude ?? ""} onChange={(e) => setForm((f) => ({ ...f, latitude: e.target.value || null }))} placeholder={translate("-27.595")} />
          </Field>
          <Field label={translate("Longitude")} htmlFor="longitude">
            <Input id="longitude" inputMode="decimal" value={form.longitude ?? ""} onChange={(e) => setForm((f) => ({ ...f, longitude: e.target.value || null }))} placeholder={translate("-48.548")} />
          </Field>
        </div>
        {current?.geocode_source ? <p className="mt-2 text-xs text-ink-3">{translate("Origem: ")}{translate(current.geocode_source === "manual" ? "informada por você" : current.geocode_source)}{translate(" · ")}{translate(formatDateTime(current.geocoded_at))}</p> : null}
      </div>
      <Button onClick={() => save.mutate({ id: current?.id, body: { ...form, latitude: form.latitude || null, longitude: form.longitude || null } }, { onSuccess: () => { setDraft(null); toast.success(translate("Endereço salvo")); } })} loading={save.isPending}>
        <Save aria-hidden className="size-4" />{translate(" Salvar endereço")}</Button>
    </SectionCard>
  );
}

function VehicleSection() {
  useLocale();
  const vehicles = useVehicles();
  const save = useSaveVehicle();
  const current = vehicles.data?.[0];
  const [draft, setDraft] = useState<Schemas["VehicleIn"] | null>(null);
  const base: Schemas["VehicleIn"] = current
    ? { name: current.name, fuel_type: current.fuel_type, km_per_liter: current.km_per_liter, fuel_price_per_liter: current.fuel_price_per_liter, is_primary: true }
    : { name: "Meu carro", fuel_type: "gasolina", km_per_liter: "11", fuel_price_per_liter: "6.29", is_primary: true };
  const form = draft ?? base;
  const setForm = (update: (f: Schemas["VehicleIn"]) => Schemas["VehicleIn"]) => setDraft((d) => update(d ?? base));
  const kmpl = Number(String(form.km_per_liter).replace(",", "."));
  const price = Number(String(form.fuel_price_per_liter).replace(",", "."));
  const example = kmpl > 0 && price >= 0 ? (20 / kmpl) * price : null;
  return (
    <SectionCard id="veiculo" icon={Car} title={translate("Veículo")} description={translate("Consumo e preço do combustível entram no custo de ida e volta.")}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={translate("Nome")} htmlFor="vehicle_name">
          <Input id="vehicle_name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </Field>
        <Field label={translate("Combustível")} htmlFor="fuel_type">
          <Select id="fuel_type" value={form.fuel_type} onChange={(e) => setForm((f) => ({ ...f, fuel_type: e.target.value as Schemas["VehicleIn"]["fuel_type"] }))}>
            <option value="gasolina">{translate("Gasolina")}</option>
            <option value="etanol">{translate("Etanol")}</option>
            <option value="diesel">{translate("Diesel")}</option>
            <option value="gnv">{translate("GNV")}</option>
            <option value="flex">{translate("Flex")}</option>
          </Select>
        </Field>
        <Field label={translate("Consumo (km/l)")} htmlFor="km_per_liter">
          <Input id="km_per_liter" inputMode="decimal" value={String(form.km_per_liter)} onChange={(e) => setForm((f) => ({ ...f, km_per_liter: e.target.value }))} />
        </Field>
        <Field label={translate("Preço do combustível (R$/l)")} htmlFor="fuel_price">
          <Input id="fuel_price" inputMode="decimal" value={String(form.fuel_price_per_liter)} onChange={(e) => setForm((f) => ({ ...f, fuel_price_per_liter: e.target.value }))} />
        </Field>
      </div>
      <InlineAlert tone="info" title={translate(<span className="inline-flex items-center gap-2"><Calculator aria-hidden className="size-4" />{translate(" Como calculamos")}</span>)}>{translate("custo = distância de ida e volta ÷ consumo × preço do combustível + pedágios.")}{translate(example !== null ? ` Exemplo: 20 km ÷ ${kmpl.toLocaleString("pt-BR")} km/l × ${money(price)}/l = ${money(example)}.` : "")}
      </InlineAlert>
      <Button onClick={() => save.mutate({ id: current?.id, body: { ...form, km_per_liter: String(kmpl), fuel_price_per_liter: String(price) } }, { onSuccess: () => { setDraft(null); toast.success(translate("Veículo salvo")); } })} loading={save.isPending} disabled={!(kmpl > 0)}>
        <Save aria-hidden className="size-4" />{translate(" Salvar veículo")}</Button>
    </SectionCard>
  );
}

function SecuritySection() {
  useLocale();
  const me = useMe();
  const client = useQueryClient();
  const sessions = useQuery({ queryKey: keys.sessions, queryFn: () => unwrap(api.GET("/api/v1/auth/sessions")) });
  const [codesOpen, setCodesOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);

  async function revoke(id: string) {
    await unwrap(api.DELETE("/api/v1/auth/sessions/{session_id}", { params: { path: { session_id: id } } }));
    void client.invalidateQueries({ queryKey: keys.sessions });
  }
  async function revokeOthers() {
    await unwrap(api.POST("/api/v1/auth/sessions/revoke-others"));
    void client.invalidateQueries({ queryKey: keys.sessions });
    toast.success(translate("Outras sessões encerradas"));
  }
  async function regenerate() {
    try {
      const result = await unwrap(api.POST("/api/v1/auth/recovery-codes", { body: { password } }));
      setCodes(result.recovery_codes);
      setPassword("");
      void client.invalidateQueries({ queryKey: keys.me });
    } catch (error) {
      toast.error(translate(errorMessage(error)));
    }
  }

  return (
    <SectionCard id="seguranca" icon={ShieldCheck} title={translate("Segurança")}>
      <div>
        <h3 className="mb-2 font-semibold">{translate("Alterar senha")}</h3>
        <ChangePasswordForm onDone={() => void client.invalidateQueries({ queryKey: keys.sessions })} />
      </div>
      <div className="border-t border-line pt-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">{translate("Sessões ativas")}</h3>
          <Button variant="ghost" size="sm" onClick={() => void revokeOthers()}>
            <LogOut aria-hidden className="size-4" />{translate(" Encerrar as outras")}</Button>
        </div>
        <ul className="space-y-2">
          {(sessions.data ?? []).map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <MonitorSmartphone aria-hidden className="size-4 text-ink-3" />
                <span>
                  <span className="font-semibold">{translate(s.client_label ?? "Navegador")}</span> {s.current ? <Badge tone="brand">{translate("esta sessão")}</Badge> : null}
                  <span className="block text-xs text-ink-3">{translate("ativa ")}{translate(ago(s.last_seen_at))}{translate(" · expira ")}{translate(formatDateTime(s.expires_at))}</span>
                </span>
              </span>
              {!s.current ? (
                <Button variant="ghost" size="sm" onClick={() => void revoke(s.id)}>{translate("Encerrar")}</Button>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
      <div className="border-t border-line pt-4">
        <h3 className="font-semibold">{translate("Códigos de recuperação")}</h3>
        <p className="mb-2 text-sm text-ink-3">{translate("Restam ")}{translate(me.data?.recovery_codes_remaining ?? "—")}{translate(" códigos. Gerar novos invalida os anteriores.")}</p>
        <Button variant="secondary" size="sm" onClick={() => setCodesOpen(true)}>
          <KeyRound aria-hidden className="size-4" />{translate(" Gerar novos códigos")}</Button>
      </div>
      <Dialog open={codesOpen} onOpenChange={(open) => { setCodesOpen(open); if (!open) setCodes(null); }} title={translate("Novos códigos de recuperação")} description={translate(codes ? undefined : "Confirme sua senha para gerar novos códigos.")}>
        {codes ? (
          <RecoveryCodes codes={codes} onDone={() => { setCodesOpen(false); setCodes(null); }} />
        ) : (
          <div className="space-y-3">
            <Field label={translate("Senha")} htmlFor="confirm_password">
              <Input id="confirm_password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Button onClick={() => void regenerate()} disabled={!password}>{translate("Gerar")}</Button>
          </div>
        )}
      </Dialog>
    </SectionCard>
  );
}

export function ProfilePage() {
  useLocale();
  useEffect(() => {
    if (window.location.hash) document.querySelector(window.location.hash)?.scrollIntoView({ block: "start" });
  }, []);
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader title={translate("Perfil")} description={translate("Preferências, endereço, veículo e segurança da sua conta.")} />
      <Preferences />
      <AddressSection />
      <VehicleSection />
      <SecuritySection />
    </div>
  );
}
