// Minimal shadcn-style primitives (Tailwind), enough for this dashboard.
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function cn(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "outline" | "ghost" }) {
  const styles = {
    default: "border-sketch-ink bg-sketch-yellow text-sketch-ink shadow-[4px_4px_0_rgba(48,42,37,0.2)] hover:-rotate-1 hover:bg-sketch-blue disabled:bg-sketch-grid",
    outline: "border-sketch-ink bg-sketch-paper text-sketch-ink shadow-[3px_3px_0_rgba(48,42,37,0.16)] hover:rotate-1 hover:bg-sketch-green",
    ghost: "border-transparent text-sketch-ink hover:border-sketch-ink hover:bg-sketch-paper",
  }[variant];
  return (
    <button
      className={cn(
        "font-hand rounded-[15px_11px_14px_12px] border-2 px-4 py-2 text-sm font-bold transition-all active:translate-x-0.5 active:translate-y-0.5 active:shadow-none disabled:cursor-not-allowed",
        styles,
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("sketch-card bg-sketch-paper", className)}
      {...props}
    />
  );
}

export function Badge({
  className,
  tone = "slate",
  children,
}: {
  className?: string;
  tone?: "slate" | "green" | "red" | "amber" | "blue" | "yellow" | "black";
  children: ReactNode;
}) {
  const tones = {
    slate: "bg-sketch-paper text-sketch-ink",
    green: "bg-sketch-green text-sketch-ink",
    red: "bg-sketch-pink text-sketch-ink",
    amber: "bg-sketch-yellow text-sketch-ink",
    yellow: "bg-sketch-yellow text-sketch-ink",
    blue: "bg-sketch-blue text-sketch-ink",
    black: "bg-sketch-ink text-white",
  }[tone];
  return (
    <span
      className={cn("font-hand inline-block rounded-[12px_9px_13px_8px] border border-sketch-ink px-2 py-0.5 text-xs font-bold", tones, className)}
    >
      {children}
    </span>
  );
}

export function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="font-hand mb-1 block text-xs font-bold text-sketch-muted">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-[14px_10px_16px_11px] border-2 border-sketch-ink bg-sketch-paper px-3 py-2 text-sm shadow-[3px_3px_0_rgba(48,42,37,0.1)] focus:bg-sketch-yellow/30 focus:outline-none";
