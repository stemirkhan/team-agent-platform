import { cva, type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-xl text-sm font-semibold transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-r from-brand-700 to-brand-600 text-white shadow-sm shadow-brand-300/60 hover:from-brand-800 hover:to-brand-700 dark:from-brand-500 dark:to-brand-600 dark:shadow-brand-900/50 dark:hover:from-brand-400 dark:hover:to-brand-500",
        secondary:
          "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 ring-1 ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800 hover:ring-slate-400 dark:hover:ring-slate-500",
        ghost: "bg-transparent text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
      },
      size: {
        sm: "h-9 px-3",
        md: "h-10 px-4",
        lg: "h-11 px-5"
      }
    },
    defaultVariants: {
      variant: "primary",
      size: "md"
    }
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);

Button.displayName = "Button";
