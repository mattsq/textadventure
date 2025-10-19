import React from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export interface PaginationProps {
  readonly currentPage: number;
  readonly totalPages: number;
  readonly onPageChange: (page: number) => void;
  readonly className?: string;
  readonly pageWindow?: number;
  readonly ariaLabel?: string;
}

const baseButtonClasses =
  "inline-flex h-8 min-w-[2rem] items-center justify-center rounded border px-2 text-xs font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/50";

const defaultButtonClasses =
  "border-slate-800 bg-slate-900/70 text-slate-200 hover:border-indigo-500/60 hover:text-white";

const disabledButtonClasses =
  "cursor-not-allowed border-slate-900 text-slate-600 hover:border-slate-900 hover:text-slate-600";

const activeButtonClasses =
  "border-indigo-500/60 bg-indigo-500/20 text-white";

interface PageControlButtonProps {
  readonly label: React.ReactNode;
  readonly targetPage: number;
  readonly disabled?: boolean;
  readonly isActive?: boolean;
  readonly onSelect: (page: number) => void;
}

const PageControlButton: React.FC<PageControlButtonProps> = ({
  label,
  targetPage,
  disabled = false,
  isActive = false,
  onSelect,
}) => {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => {
        if (!disabled) {
          onSelect(targetPage);
        }
      }}
      className={classNames(
        baseButtonClasses,
        isActive ? activeButtonClasses : defaultButtonClasses,
        disabled ? disabledButtonClasses : undefined,
      )}
      aria-current={isActive ? "page" : undefined}
    >
      {label}
    </button>
  );
};

const buildPageWindow = (
  currentPage: number,
  totalPages: number,
  windowSize: number,
): readonly (number | "ellipsis")[] => {
  if (totalPages <= windowSize + 2) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const halfWindow = Math.floor(windowSize / 2);
  let start = Math.max(2, currentPage - halfWindow);
  let end = Math.min(totalPages - 1, start + windowSize - 1);
  start = Math.max(2, end - windowSize + 1);

  const pages: (number | "ellipsis")[] = [1];

  if (start > 2) {
    pages.push("ellipsis");
  }

  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }

  if (end < totalPages - 1) {
    pages.push("ellipsis");
  }

  pages.push(totalPages);

  return pages;
};

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  className,
  pageWindow = 5,
  ariaLabel = "Pagination",
}) => {
  const safeTotalPages = Math.max(1, totalPages);
  const safeCurrentPage = Math.min(
    Math.max(1, currentPage),
    safeTotalPages,
  );

  const pages = React.useMemo(
    () => buildPageWindow(safeCurrentPage, safeTotalPages, pageWindow),
    [safeCurrentPage, safeTotalPages, pageWindow],
  );

  const handlePageChange = React.useCallback(
    (page: number) => {
      const nextPage = Math.min(Math.max(1, page), safeTotalPages);
      if (nextPage !== safeCurrentPage) {
        onPageChange(nextPage);
      }
    },
    [onPageChange, safeCurrentPage, safeTotalPages],
  );

  return (
    <nav
      aria-label={ariaLabel}
      className={classNames(
        "flex flex-wrap items-center gap-2",
        className,
      )}
    >
      <div className="flex items-center gap-1">
        <PageControlButton
          label="First"
          targetPage={1}
          disabled={safeCurrentPage === 1}
          onSelect={handlePageChange}
        />
        <PageControlButton
          label="Previous"
          targetPage={safeCurrentPage - 1}
          disabled={safeCurrentPage === 1}
          onSelect={handlePageChange}
        />
      </div>
      <div className="flex items-center gap-1">
        {pages.map((page, index) =>
          page === "ellipsis" ? (
            <span
              key={`ellipsis-${index}`}
              className="px-2 text-xs font-semibold text-slate-500"
              aria-hidden
            >
              …
            </span>
          ) : (
            <PageControlButton
              key={page}
              label={page}
              targetPage={page}
              isActive={page === safeCurrentPage}
              onSelect={handlePageChange}
            />
          ),
        )}
      </div>
      <div className="flex items-center gap-1">
        <PageControlButton
          label="Next"
          targetPage={safeCurrentPage + 1}
          disabled={safeCurrentPage === safeTotalPages}
          onSelect={handlePageChange}
        />
        <PageControlButton
          label="Last"
          targetPage={safeTotalPages}
          disabled={safeCurrentPage === safeTotalPages}
          onSelect={handlePageChange}
        />
      </div>
      <span className="ml-2 text-xs text-slate-400">
        Page {safeCurrentPage} of {safeTotalPages}
      </span>
    </nav>
  );
};

export default Pagination;
