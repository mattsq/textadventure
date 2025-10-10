import React from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export type CardVariant = "default" | "subtle" | "transparent";

const variantClasses: Record<CardVariant, string> = {
  default:
    "border-slate-800/70 bg-slate-900/70 shadow-lg shadow-slate-950/30", // elevated card
  subtle: "border-slate-800/60 bg-slate-900/40", // matches subtle panels
  transparent: "border-transparent bg-transparent", // allow backgrounds to show through
};

export interface CardProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  readonly variant?: CardVariant;
  readonly title?: React.ReactNode;
  readonly description?: React.ReactNode;
  readonly icon?: React.ReactNode;
  readonly actions?: React.ReactNode;
  readonly footer?: React.ReactNode;
  readonly compact?: boolean;
}

export const Card: React.FC<CardProps> = ({
  variant = "default",
  title,
  description,
  icon,
  actions,
  footer,
  compact = false,
  className,
  children,
  ...props
}) => {
  const hasHeader = title || description || icon || actions;
  return (
    <div
      {...props}
      className={classNames(
        "flex flex-col overflow-hidden rounded-xl border transition",
        "hover:border-indigo-400/30 hover:shadow-xl hover:shadow-indigo-950/30",
        variantClasses[variant],
        compact ? "gap-3 p-4" : "gap-4 p-6",
        className,
      )}
    >
      {hasHeader ? (
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="flex flex-1 items-start gap-3">
            {icon ? <span className="mt-1 text-lg text-indigo-300" aria-hidden>{icon}</span> : null}
            <div className="flex flex-col gap-1">
              {title ? <h3 className="text-base font-semibold text-slate-50">{title}</h3> : null}
              {description ? <p className="text-sm leading-relaxed text-slate-300">{description}</p> : null}
            </div>
          </div>
          {actions ? <div className="flex items-center gap-2 text-sm">{actions}</div> : null}
        </div>
      ) : null}

      {children ? <div className="flex flex-col gap-3 text-sm text-slate-200">{children}</div> : null}

      {footer ? (
        <div className="border-t border-slate-800/60 pt-3 text-xs text-slate-400">{footer}</div>
      ) : null}
    </div>
  );
};

export default Card;
