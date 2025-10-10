import React from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

const defaultSeparator = (
  <svg
    className="h-3 w-3 text-slate-600"
    viewBox="0 0 12 12"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden
  >
    <path
      d="M4.25 2.25L7.75 6L4.25 9.75"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export interface BreadcrumbItem {
  readonly id: string;
  readonly label: React.ReactNode;
  readonly href?: string;
  readonly onClick?: () => void;
  readonly icon?: React.ReactNode;
  readonly current?: boolean;
}

export interface BreadcrumbsProps {
  readonly items: readonly BreadcrumbItem[];
  readonly separator?: React.ReactNode;
  readonly ariaLabel?: string;
  readonly className?: string;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({
  items,
  separator = defaultSeparator,
  ariaLabel = "Breadcrumb",
  className,
}) => {
  if (items.length === 0) {
    return null;
  }

  return (
    <nav className={classNames("text-xs text-slate-400", className)} aria-label={ariaLabel}>
      <ol className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => {
          const isCurrent = item.current ?? index === items.length - 1;
          const content = (() => {
            if (isCurrent) {
              return (
                <span className="inline-flex items-center gap-2 font-semibold text-slate-100" aria-current="page">
                  {item.icon ? (
                    <span className="text-slate-300" aria-hidden>
                      {item.icon}
                    </span>
                  ) : null}
                  <span className="truncate">{item.label}</span>
                </span>
              );
            }

            if (item.href) {
              return (
                <a
                  href={item.href}
                  className="inline-flex items-center gap-2 transition hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                >
                  {item.icon ? (
                    <span className="text-slate-500" aria-hidden>
                      {item.icon}
                    </span>
                  ) : null}
                  <span className="truncate">{item.label}</span>
                </a>
              );
            }

            if (item.onClick) {
              return (
                <button
                  type="button"
                  onClick={item.onClick}
                  className="inline-flex items-center gap-2 transition hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                >
                  {item.icon ? (
                    <span className="text-slate-500" aria-hidden>
                      {item.icon}
                    </span>
                  ) : null}
                  <span className="truncate">{item.label}</span>
                </button>
              );
            }

            return (
              <span className="inline-flex items-center gap-2 text-slate-300">
                {item.icon ? (
                  <span className="text-slate-500" aria-hidden>
                    {item.icon}
                  </span>
                ) : null}
                <span className="truncate">{item.label}</span>
              </span>
            );
          })();

          return (
            <li key={item.id} className="inline-flex items-center gap-2">
              {index > 0 ? <span aria-hidden>{separator}</span> : null}
              {content}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default Breadcrumbs;
