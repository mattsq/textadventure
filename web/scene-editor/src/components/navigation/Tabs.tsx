import React from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export type TabVariant = "underline" | "pill";
export type TabSize = "sm" | "md";

export interface TabItem {
  readonly id: string;
  readonly label: React.ReactNode;
  readonly description?: React.ReactNode;
  readonly badge?: React.ReactNode;
  readonly disabled?: boolean;
}

export interface TabsProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange" | "children"> {
  readonly items: readonly TabItem[];
  readonly activeTab: string;
  readonly onTabChange?: (id: string) => void;
  readonly variant?: TabVariant;
  readonly size?: TabSize;
  readonly fullWidth?: boolean;
  readonly ariaLabel?: string;
}

interface VariantStyle {
  readonly list: string;
  readonly base: string;
  readonly active: string;
  readonly inactive: string;
  readonly disabled: string;
}

const variantStyles: Record<TabVariant, VariantStyle> = {
  underline: {
    list: "flex flex-wrap items-center gap-2 border-b border-slate-800/80",
    base: "-mb-px border-b-2 border-transparent text-sm font-medium",
    active: "border-indigo-400 text-slate-50",
    inactive: "text-slate-300 hover:text-slate-100",
    disabled: "cursor-not-allowed text-slate-600",
  },
  pill: {
    list: "flex flex-wrap items-center gap-2 rounded-xl border border-slate-800/70 bg-slate-900/40 p-1",
    base: "rounded-lg text-sm font-medium",
    active: "bg-indigo-500/25 text-slate-50 shadow-inner shadow-indigo-900/30",
    inactive: "text-slate-300 hover:text-slate-100 hover:bg-indigo-500/10",
    disabled: "cursor-not-allowed text-slate-600",
  },
};

const sizeClasses: Record<TabSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export const Tabs: React.FC<TabsProps> = ({
  items,
  activeTab,
  onTabChange,
  variant = "underline",
  size = "md",
  fullWidth = false,
  ariaLabel,
  className,
  ...props
}) => {
  if (items.length === 0) {
    return null;
  }

  const styles = variantStyles[variant];

  return (
    <div {...props} className={classNames("flex flex-col gap-2", className)}>
      <div
        role="tablist"
        aria-label={ariaLabel}
        className={classNames(styles.list, fullWidth ? "w-full" : undefined)}
      >
        {items.map((item) => {
          const isActive = item.id === activeTab;
          const tabClassName = classNames(
            "group relative inline-flex items-center gap-3 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900",
            sizeClasses[size],
            styles.base,
            isActive ? styles.active : styles.inactive,
            item.disabled ? styles.disabled : undefined,
            fullWidth ? "flex-1 justify-between" : "justify-between",
          );

          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              tabIndex={item.disabled ? -1 : isActive ? 0 : -1}
              className={tabClassName}
              onClick={() => {
                if (item.disabled) {
                  return;
                }
                if (item.id !== activeTab) {
                  onTabChange?.(item.id);
                }
              }}
              disabled={item.disabled}
            >
              <span className="flex min-w-0 flex-col text-left">
                <span className="truncate font-semibold">{item.label}</span>
                {item.description ? (
                  <span className="mt-0.5 text-xs font-normal text-slate-400">
                    {item.description}
                  </span>
                ) : null}
              </span>
              {item.badge ? <span className="shrink-0">{item.badge}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default Tabs;
