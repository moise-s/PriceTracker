import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-[background,box-shadow,color,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-55 select-none whitespace-nowrap",
  {
    variants: {
      variant: {
        primary: "bg-brand text-on-brand shadow-[0_1px_0_rgb(255_255_255/0.2)_inset,0_6px_16px_-8px_rgb(22_85_58/0.8)] hover:bg-brand-strong",
        secondary: "bg-surface text-ink ring-1 ring-line-strong hover:bg-surface-2 hover:ring-ink-3/40",
        ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink",
        subtle: "bg-brand-soft text-brand-ink hover:bg-brand-soft/70",
        danger: "bg-danger text-on-danger hover:bg-danger/90",
        accent: "bg-accent text-on-accent hover:bg-accent/90",
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

export type ButtonVariants = VariantProps<typeof buttonStyles>;

export function buttonClass(options: ButtonVariants & { className?: string } = {}): string {
  return cn(buttonStyles({ variant: options.variant, size: options.size }), options.className);
}
