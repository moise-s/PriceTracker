import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { Loader2, Minus, Plus, X } from "lucide-react";
import { Checkbox as CheckboxPrimitive, Dialog as DialogPrimitive, Switch as SwitchPrimitive, Tabs as TabsPrimitive } from "radix-ui";
import { type ComponentProps, forwardRef, type ReactNode, useId } from "react";
import { twMerge } from "tailwind-merge";
import type { Tone } from "@/lib/labels";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// --- Button ---------------------------------------------------------------------------------

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-[background,box-shadow,color,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-55 select-none whitespace-nowrap",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white shadow-[0_1px_0_rgb(255_255_255/0.2)_inset,0_6px_16px_-8px_rgb(22_85_58/0.8)] hover:bg-brand-strong",
        secondary: "bg-surface text-ink ring-1 ring-line-strong hover:bg-surface-2 hover:ring-ink-3/40",
        ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink",
        subtle: "bg-brand-soft text-brand-ink hover:bg-brand-soft/70",
        danger: "bg-danger text-white hover:bg-danger/90",
        accent: "bg-accent text-white hover:bg-accent/90",
      },
      size: {
        sm: "h-9 px-3.5 text-sm",
        md: "h-11 px-5 text-[15px]",
        lg: "h-13 px-6 text-base",
        icon: "size-10",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends ComponentProps<"button">, VariantProps<typeof buttonStyles> {
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, loading, children, disabled, type = "button", ...props },
  ref,
) {
  return (
    <button ref={ref} type={type} className={cn(buttonStyles({ variant, size }), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {loading ? <Loader2 aria-hidden className="size-4 animate-spin" /> : null}
      {children}
    </button>
  );
});

export function buttonClass(options: VariantProps<typeof buttonStyles> & { className?: string } = {}): string {
  return cn(buttonStyles({ variant: options.variant, size: options.size }), options.className);
}

// --- Card / surfaces ------------------------------------------------------------------------------

export function Card({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("rounded-xl border border-line bg-surface shadow-card", className)} {...props} />;
}

export function Section({ title, description, action, children, className, id }: { title: ReactNode; description?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={cn("space-y-3", className)} id={id}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id={headingId} className="text-lg font-semibold text-ink sm:text-xl">
            {title}
          </h2>
          {description ? <p className="mt-0.5 text-sm text-ink-3">{description}</p> : null}
        </div>
        {action}
      </div>
      {children}
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
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset whitespace-nowrap", toneStyles[tone], className)}>
      {Icon ? <Icon aria-hidden className={cn("size-3.5 shrink-0", spin && "animate-spin")} /> : null}
      {children}
    </span>
  );
}

// --- Form controls ------------------------------------------------------------------------------------

export function Label({ className, ...props }: ComponentProps<"label">) {
  return <label className={cn("text-sm font-semibold text-ink", className)} {...props} />;
}

const fieldControl =
  "w-full rounded-md border border-line-strong bg-surface px-3.5 text-[15px] text-ink placeholder:text-ink-3/80 transition-colors focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/20 disabled:opacity-60 aria-invalid:border-danger aria-invalid:ring-danger/15";

export const Input = forwardRef<HTMLInputElement, ComponentProps<"input">>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(fieldControl, "h-11", className)} {...props} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, ComponentProps<"textarea">>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn(fieldControl, "min-h-24 py-2.5", className)} {...props} />;
});

export const Select = forwardRef<HTMLSelectElement, ComponentProps<"select">>(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn(fieldControl, "h-11 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2216%22 height=%2216%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23636a65%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:16px] bg-[right_0.85rem_center] bg-no-repeat pr-10", className)} {...props}>
      {children}
    </select>
  );
});

export function Field({ label, hint, error, children, htmlFor, className }: { label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; htmlFor: string; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm font-medium text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-sm text-ink-3">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Checkbox({ className, ...props }: ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root className={cn("peer grid size-5 shrink-0 place-content-center rounded-[6px] border-2 border-line-strong bg-surface transition-colors data-[state=checked]:border-brand data-[state=checked]:bg-brand", className)} {...props}>
      <CheckboxPrimitive.Indicator>
        <svg viewBox="0 0 16 16" className="size-3.5 text-white" aria-hidden>
          <path d="M3.5 8.5 6.5 11.5 12.5 4.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export function Switch({ className, ...props }: ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root className={cn("relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-line-strong transition-colors data-[state=checked]:bg-brand", className)} {...props}>
      <SwitchPrimitive.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
    </SwitchPrimitive.Root>
  );
}

export function SwitchRow({ id, label, description, checked, onCheckedChange, disabled }: { id: string; label: ReactNode; description?: ReactNode; checked: boolean; onCheckedChange: (value: boolean) => void; disabled?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div>
        <label htmlFor={id} className="text-[15px] font-semibold text-ink">
          {label}
        </label>
        {description ? <p className="text-sm text-ink-3">{description}</p> : null}
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  );
}

// --- Quantity stepper ---------------------------------------------------------------------------------

export function Stepper({ value, onChange, min = 0, step = 1, label, unitLabel, disabled }: { value: number; onChange: (value: number) => void; min?: number; step?: number; label: string; unitLabel?: string; disabled?: boolean }) {
  const format = (n: number) => (Number.isInteger(n) ? String(n) : n.toLocaleString("pt-BR", { maximumFractionDigits: 3 }));
  return (
    <div className="inline-flex items-center rounded-full bg-surface ring-1 ring-line-strong" role="group" aria-label={label}>
      <button type="button" className="grid size-9 place-content-center rounded-full text-ink-2 hover:bg-surface-3 disabled:opacity-40" onClick={() => onChange(Math.max(min, +(value - step).toFixed(3)))} disabled={disabled || value <= min} aria-label={`Diminuir ${label}`}>
        <Minus className="size-4" aria-hidden />
      </button>
      <output className="min-w-12 px-1 text-center text-sm font-bold tabular" aria-live="polite">
        {format(value)}
        {unitLabel ? <span className="ml-0.5 font-medium text-ink-3">{unitLabel}</span> : null}
      </output>
      <button type="button" className="grid size-9 place-content-center rounded-full text-ink-2 hover:bg-surface-3 disabled:opacity-40" onClick={() => onChange(+(value + step).toFixed(3))} disabled={disabled} aria-label={`Aumentar ${label}`}>
        <Plus className="size-4" aria-hidden />
      </button>
    </div>
  );
}

// --- Progress / skeleton / states ----------------------------------------------------------------------

export function Progress({ value, max, label, tone = "brand", className }: { value: number; max: number; label: string; tone?: "brand" | "accent" | "warn"; className?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const color = tone === "brand" ? "bg-brand" : tone === "accent" ? "bg-accent" : "bg-warn";
  return (
    <div className={cn("h-2.5 w-full overflow-hidden rounded-full bg-surface-3", className)} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={cn("h-full rounded-full transition-[width] duration-500", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton h-4", className)} />;
}

export function LoadingBlock({ label = "Carregando", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cn("h-20 w-full", i % 2 === 1 && "h-16")} />
      ))}
      <span className="sr-only">{label}…</span>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action, className }: { icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-10 text-center", className)}>
      <span className="mb-3 grid size-14 place-content-center rounded-2xl bg-brand-soft text-brand">
        <Icon aria-hidden className="size-7" />
      </span>
      <h3 className="text-lg font-semibold">{title}</h3>
      {children ? <div className="mt-1 max-w-md text-[15px] text-ink-2">{children}</div> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function InlineAlert({ tone = "info", title, children, action, className }: { tone?: Tone; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex flex-col gap-2 rounded-lg px-4 py-3 ring-1 ring-inset sm:flex-row sm:items-center sm:justify-between", toneStyles[tone])}>
      <div className={cn("text-sm", className)}>
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="opacity-95">{children}</div> : null}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <InlineAlert tone="danger" title="Não foi possível carregar" action={onRetry ? <Button size="sm" variant="secondary" onClick={onRetry}>Tentar de novo</Button> : undefined}>
      {error}
    </InlineAlert>
  );
}

// --- Dialog / Sheet ------------------------------------------------------------------------------------

export function Dialog({ open, onOpenChange, title, description, children, footer, size = "md" }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description?: ReactNode; children: ReactNode; footer?: ReactNode; size?: "md" | "lg" }) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/35 backdrop-blur-[2px] data-[state=open]:animate-rise" />
        <DialogPrimitive.Content className={cn("fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] flex-col rounded-t-2xl bg-surface shadow-lift outline-none sm:inset-auto sm:top-1/2 sm:left-1/2 sm:w-[calc(100%-2rem)] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl", size === "md" ? "sm:max-w-lg" : "sm:max-w-2xl")}>
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 pt-5 pb-4">
            <div>
              <DialogPrimitive.Title className="font-display text-xl font-semibold">{title}</DialogPrimitive.Title>
              {description ? <DialogPrimitive.Description className="mt-1 text-sm text-ink-3">{description}</DialogPrimitive.Description> : <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>}
            </div>
            <DialogPrimitive.Close className={buttonClass({ variant: "ghost", size: "icon-sm" })} aria-label="Fechar">
              <X className="size-4" aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer ? <div className="safe-bottom flex flex-wrap justify-end gap-2 border-t border-line px-5 pt-3">{footer}</div> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

// --- Tabs -------------------------------------------------------------------------------------------------

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return <TabsPrimitive.List className={cn("scrollbar-none flex gap-1 overflow-x-auto rounded-full bg-surface-3 p-1", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return <TabsPrimitive.Trigger className={cn("h-9 shrink-0 rounded-full px-4 text-sm font-semibold text-ink-2 transition-colors hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-card", className)} {...props} />;
}

export const TabsContent = TabsPrimitive.Content;

export function Spinner({ label = "Carregando" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-ink-3">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span>{label}…</span>
    </span>
  );
}
