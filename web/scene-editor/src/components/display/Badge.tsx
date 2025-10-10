import React from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export type BadgeVariant =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger";

export type BadgeSize = "sm" | "md";

const variantClasses: Record<BadgeVariant, string> = {
  neutral:
    "border-slate-700/70 bg-slate-900/70 text-slate-200 shadow-inner shadow-slate-950/40",
  info: "border-sky-500/40 bg-sky-500/20 text-sky-100",
  success: "border-emerald-500/40 bg-emerald-500/20 text-emerald-100",
  warning: "border-amber-500/40 bg-amber-500/20 text-amber-100",
  danger: "border-rose-500/40 bg-rose-500/20 text-rose-100",
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-sm",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  readonly variant?: BadgeVariant;
  readonly size?: BadgeSize;
  readonly leadingIcon?: React.ReactNode;
  readonly trailingIcon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = "neutral",
  size = "md",
  leadingIcon,
  trailingIcon,
  className,
  children,
  ...props
}) => {
  return (
    <span
      {...props}
      className={classNames(
        "inline-flex items-center gap-1 rounded-full border font-medium", // base
        "uppercase tracking-wide", // subtle emphasis
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {leadingIcon ? <span className="flex items-center" aria-hidden>{leadingIcon}</span> : null}
      <span>{children}</span>
      {trailingIcon ? <span className="flex items-center" aria-hidden>{trailingIcon}</span> : null}
    </span>
  );
};

export default Badge;
