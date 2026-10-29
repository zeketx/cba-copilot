import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
};

export function Button({ variant = "primary", className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center rounded-full px-3 py-1.5 text-sm transition-colors disabled:opacity-50",
        variant === "primary"
          ? "bg-ink text-paper hover:bg-ink/90"
          : "border border-rule bg-paper text-ink hover:bg-chip",
        className,
      )}
      {...props}
    />
  );
}
