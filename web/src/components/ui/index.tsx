import { getLocale, translate, useLocale } from "@/lib/i18n";
import { Loader2, Minus, Plus, X } from "lucide-react";
import { Checkbox as CheckboxPrimitive, Dialog as DialogPrimitive, Switch as SwitchPrimitive, Tabs as TabsPrimitive } from "radix-ui";
import { type ComponentProps, forwardRef, type ReactNode, useId } from "react";
import type { Tone } from "@/lib/labels";
import { buttonClass, buttonStyles, type ButtonVariants, cn } from "./utils";

// --- Button ---------------------------------------------------------------------------------

export interface ButtonProps extends ComponentProps<"button">, ButtonVariants {
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, loading, children, disabled, type = "button", ...props },
  ref,
) {
  useLocale();
  return (
    <button ref={ref} type={type} className={cn(buttonStyles({ variant, size }), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {loading ? <Loader2 aria-hidden className="size-4 animate-spin" /> : null}
      {translate(children)}
    </button>
  );
});

// --- Card / surfaces ------------------------------------------------------------------------------

export function Card({ className, as: Tag = "div", ...props }: ComponentProps<"div"> & { as?: "div" | "section" | "article" }) {
  useLocale();
  return <Tag className={cn("rounded-xl border border-line bg-surface shadow-card", className)} {...props} />;
}

export function Section({ title, description, action, children, className, id }: { title: ReactNode; description?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  useLocale();
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={cn("space-y-3", className)} id={id}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id={headingId} className="text-lg font-semibold text-ink sm:text-xl">
            {translate(title)}
          </h2>
          {description ? <p className="mt-0.5 text-sm text-ink-3">{translate(description)}</p> : null}
        </div>
        {translate(action)}
      </div>
      {translate(children)}
    </section>
  );
}

// --- Badge ------------------------------------------------------------------------------------------

const toneStyles: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2 ring-line",
  brand: "bg-brand-soft text-brand-ink ring-brand/15",
  accent: "bg-accent-soft text-accent-ink ring-accent/20",
  warn: "bg-warn-soft text-warn ring-warn/20",
  danger: "bg-danger-soft text-danger ring-danger/20",
  info: "bg-info-soft text-info ring-info/20",
};

export function Badge({ tone = "neutral", icon: Icon, children, className, spin }: { tone?: Tone; icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; children: ReactNode; className?: string; spin?: boolean }) {
  useLocale();
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset whitespace-nowrap", toneStyles[tone], className)}>
      {Icon ? <Icon aria-hidden className={cn("size-3.5 shrink-0", spin && "animate-spin")} /> : null}
      {translate(children)}
    </span>
  );
}

// --- Form controls ------------------------------------------------------------------------------------

export function Label({ className, ...props }: ComponentProps<"label">) {
  useLocale();
  return <label className={cn("text-sm font-semibold text-ink", className)} {...props} />;
}

const fieldControl =
  "w-full rounded-md border border-line-strong bg-surface px-3.5 text-[15px] text-ink placeholder:text-ink-3/80 transition-colors focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/20 disabled:opacity-60 aria-invalid:border-danger aria-invalid:ring-danger/15";

export const Input = forwardRef<HTMLInputElement, ComponentProps<"input">>(function Input({ className, ...props }, ref) {
  useLocale();
  return <input ref={ref} className={cn(fieldControl, "h-11", className)} {...props} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, ComponentProps<"textarea">>(function Textarea({ className, ...props }, ref) {
  useLocale();
  return <textarea ref={ref} className={cn(fieldControl, "min-h-24 py-2.5", className)} {...props} />;
});

export const Select = forwardRef<HTMLSelectElement, ComponentProps<"select">>(function Select({ className, children, ...props }, ref) {
  useLocale();
  return (
    <select ref={ref} className={cn(fieldControl, "h-11 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2216%22 height=%2216%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23636a65%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:16px] bg-[right_0.85rem_center] bg-no-repeat pr-10", className)} {...props}>
      {translate(children)}
    </select>
  );
});

export function Field({ label, hint, error, children, htmlFor, className }: { label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; htmlFor: string; className?: string }) {
  useLocale();
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor}>{translate(label)}</Label>
      {translate(children)}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm font-medium text-danger">
          {translate(error)}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-sm text-ink-3">
          {translate(hint)}
        </p>
      ) : null}
    </div>
  );
}

export function Checkbox({ className, ...props }: ComponentProps<typeof CheckboxPrimitive.Root>) {
  useLocale();
  return (
    <CheckboxPrimitive.Root className={cn("peer grid size-5 shrink-0 place-content-center rounded-[6px] border-2 border-line-strong bg-surface transition-colors data-[state=checked]:border-brand data-[state=checked]:bg-brand", className)} {...props}>
      <CheckboxPrimitive.Indicator>
        <svg viewBox="0 0 16 16" className="size-3.5 text-on-brand" aria-hidden>
          <path d="M3.5 8.5 6.5 11.5 12.5 4.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export function Switch({ className, ...props }: ComponentProps<typeof SwitchPrimitive.Root>) {
  useLocale();
  return (
    <SwitchPrimitive.Root className={cn("relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-line-strong transition-colors data-[state=checked]:bg-brand", className)} {...props}>
      <SwitchPrimitive.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
    </SwitchPrimitive.Root>
  );
}

export function SwitchRow({ id, label, description, checked, onCheckedChange, disabled }: { id: string; label: ReactNode; description?: ReactNode; checked: boolean; onCheckedChange: (value: boolean) => void; disabled?: boolean }) {
  useLocale();
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div>
        <label htmlFor={id} className="text-[15px] font-semibold text-ink">
          {translate(label)}
        </label>
        {description ? <p className="text-sm text-ink-3">{translate(description)}</p> : null}
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  );
}

// --- Quantity stepper ---------------------------------------------------------------------------------

export function Stepper({ value, onChange, min = 0, step = 1, label, unitLabel, disabled }: { value: number; onChange: (value: number) => void; min?: number; step?: number; label: string; unitLabel?: string; disabled?: boolean }) {
  useLocale();
  const format = (n: number) => (Number.isInteger(n) ? String(n) : n.toLocaleString(getLocale(), { maximumFractionDigits: 3 }));
  return (
    <div className="inline-flex items-center rounded-full bg-surface ring-1 ring-line-strong" role="group" aria-label={translate(label)}>
      <button type="button" className="grid size-9 place-content-center rounded-full text-ink-2 hover:bg-surface-3 disabled:opacity-40" onClick={() => onChange(Math.max(min, +(value - step).toFixed(3)))} disabled={disabled || value <= min} aria-label={translate(`Diminuir ${label}`)}>
        <Minus className="size-4" aria-hidden />
      </button>
      <output className="min-w-12 px-1 text-center text-sm font-bold tabular" aria-live="polite">
        {translate(format(value))}
        {unitLabel ? <span className="ml-0.5 font-medium text-ink-3">{translate(unitLabel)}</span> : null}
      </output>
      <button type="button" className="grid size-9 place-content-center rounded-full text-ink-2 hover:bg-surface-3 disabled:opacity-40" onClick={() => onChange(+(value + step).toFixed(3))} disabled={disabled} aria-label={translate(`Aumentar ${label}`)}>
        <Plus className="size-4" aria-hidden />
      </button>
    </div>
  );
}

// --- Progress / skeleton / states ----------------------------------------------------------------------

export function Progress({ value, max, label, tone = "brand", className }: { value: number; max: number; label: string; tone?: "brand" | "accent" | "warn"; className?: string }) {
  useLocale();
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const color = tone === "brand" ? "bg-brand" : tone === "accent" ? "bg-accent" : "bg-warn";
  return (
    <div className={cn("h-2.5 w-full overflow-hidden rounded-full bg-surface-3", className)} role="progressbar" aria-label={translate(label)} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={cn("h-full rounded-full transition-[width] duration-500", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  useLocale();
  return <div aria-hidden className={cn("skeleton h-4", className)} />;
}

export function LoadingBlock({ label = "Carregando", rows = 3 }: { label?: string; rows?: number }) {
  useLocale();
  return (
    <div role="status" aria-label={translate(label)} className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cn("h-20 w-full", i % 2 === 1 && "h-16")} />
      ))}
      <span className="sr-only">{translate(label)}{translate("…")}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action, className }: { icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  useLocale();
  return (
    <div className={cn("flex flex-col items-center rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-10 text-center", className)}>
      <span className="mb-3 grid size-14 place-content-center rounded-2xl bg-brand-soft text-brand">
        <Icon aria-hidden className="size-7" />
      </span>
      <h3 className="text-lg font-semibold">{translate(title)}</h3>
      {children ? <div className="mt-1 max-w-md text-[15px] text-ink-2">{translate(children)}</div> : null}
      {action ? <div className="mt-5">{translate(action)}</div> : null}
    </div>
  );
}

export function InlineAlert({ tone = "info", title, children, action, className }: { tone?: Tone; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  useLocale();
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex flex-col gap-2 rounded-lg px-4 py-3 ring-1 ring-inset sm:flex-row sm:items-center sm:justify-between", toneStyles[tone])}>
      <div className={cn("text-sm", className)}>
        {title ? <p className="font-semibold">{translate(title)}</p> : null}
        {children ? <div>{translate(children)}</div> : null}
      </div>
      {translate(action)}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  useLocale();
  return (
    <InlineAlert tone="danger" title={translate("Não foi possível carregar")} action={onRetry ? <Button size="sm" variant="secondary" onClick={onRetry}>{translate("Tentar de novo")}</Button> : undefined}>
      {translate(error)}
    </InlineAlert>
  );
}

// --- Dialog / Sheet ------------------------------------------------------------------------------------

export function Dialog({ open, onOpenChange, title, description, children, footer, size = "md" }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description?: ReactNode; children: ReactNode; footer?: ReactNode; size?: "md" | "lg" }) {
  useLocale();
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/35 backdrop-blur-[2px] data-[state=open]:animate-rise" />
        <DialogPrimitive.Content className={cn("fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] flex-col rounded-t-2xl bg-surface shadow-lift outline-none sm:inset-auto sm:top-1/2 sm:left-1/2 sm:w-[calc(100%-2rem)] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl", size === "md" ? "sm:max-w-lg" : "sm:max-w-2xl")}>
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 pt-5 pb-4">
            <div>
              <DialogPrimitive.Title className="font-display text-xl font-semibold">{translate(title)}</DialogPrimitive.Title>
              {description ? <DialogPrimitive.Description className="mt-1 text-sm text-ink-3">{translate(description)}</DialogPrimitive.Description> : <DialogPrimitive.Description className="sr-only">{translate(title)}</DialogPrimitive.Description>}
            </div>
            <DialogPrimitive.Close className={buttonClass({ variant: "ghost", size: "icon-sm" })} aria-label={translate("Fechar")}>
              <X className="size-4" aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <div className="overflow-y-auto px-5 py-4">{translate(children)}</div>
          {footer ? <div className="safe-bottom flex flex-wrap justify-end gap-2 border-t border-line px-5 pt-3">{translate(footer)}</div> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

// --- Tabs -------------------------------------------------------------------------------------------------

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  useLocale();
  return <TabsPrimitive.List className={cn("scrollbar-none flex gap-1 overflow-x-auto rounded-full bg-surface-3 p-1", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  useLocale();
  return <TabsPrimitive.Trigger className={cn("h-9 shrink-0 rounded-full px-4 text-sm font-semibold text-ink-2 transition-colors hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-card", className)} {...props} />;
}

export const TabsContent = TabsPrimitive.Content;

export function Spinner({ label = "Carregando" }: { label?: string }) {
  useLocale();
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-ink-3">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span>{translate(label)}{translate("…")}</span>
    </span>
  );
}
