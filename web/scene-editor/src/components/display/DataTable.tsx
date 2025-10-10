import React from "react";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export type ColumnAlignment = "left" | "center" | "right";

export interface DataTableColumn<T> {
  readonly id: string;
  readonly header: React.ReactNode;
  readonly align?: ColumnAlignment;
  readonly className?: string;
  readonly accessor?: keyof T | ((item: T, index: number) => React.ReactNode);
  readonly render?: (item: T, index: number) => React.ReactNode;
}

export interface DataTableProps<T> {
  readonly columns: readonly DataTableColumn<T>[];
  readonly data: readonly T[];
  readonly caption?: React.ReactNode;
  readonly emptyState?: React.ReactNode;
  readonly getRowKey?: (item: T, index: number) => React.Key;
  readonly onRowClick?: (item: T, index: number) => void;
  readonly dense?: boolean;
  readonly className?: string;
}

const alignmentClasses: Record<ColumnAlignment, string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

const resolveCellValue = <T,>(
  column: DataTableColumn<T>,
  item: T,
  index: number,
): React.ReactNode => {
  if (column.render) {
    return column.render(item, index);
  }

  if (column.accessor) {
    if (typeof column.accessor === "function") {
      return column.accessor(item, index);
    }

    return (item as Record<PropertyKey, React.ReactNode>)[column.accessor];
  }

  return (item as Record<PropertyKey, React.ReactNode>)[column.id];
};

export const DataTable = <T,>({
  columns,
  data,
  caption,
  emptyState = "No records to display.",
  getRowKey,
  onRowClick,
  dense = false,
  className,
}: DataTableProps<T>): React.ReactElement => {
  const rowClassName = classNames(
    "group", // enable hover styles on children
    onRowClick ? "cursor-pointer" : undefined,
  );

  return (
    <div
      className={classNames(
        "overflow-hidden rounded-xl border border-slate-800/70 bg-slate-950/40 shadow-lg shadow-slate-950/20",
        className,
      )}
    >
      <table className="min-w-full divide-y divide-slate-800 text-sm">
        {caption ? (
          <caption className="px-6 py-4 text-left text-sm font-medium text-slate-300">
            {caption}
          </caption>
        ) : null}
        <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                scope="col"
                className={classNames(
                  "px-6 py-3 font-semibold", // baseline spacing
                  alignmentClasses[column.align ?? "left"],
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/70 text-slate-200">
          {data.length === 0 ? (
            <tr>
              <td
                className="px-6 py-6 text-center text-sm text-slate-400"
                colSpan={columns.length || 1}
              >
                {emptyState}
              </td>
            </tr>
          ) : (
            data.map((item, rowIndex) => {
              const key = getRowKey ? getRowKey(item, rowIndex) : rowIndex;
              return (
                <tr
                  key={key}
                  onClick={onRowClick ? () => onRowClick(item, rowIndex) : undefined}
                  className={rowClassName}
                >
                  {columns.map((column) => (
                    <td
                      key={column.id}
                      className={classNames(
                        dense ? "px-4 py-2" : "px-6 py-3",
                        alignmentClasses[column.align ?? "left"],
                        "transition group-hover:bg-slate-900/40",
                        column.className,
                      )}
                    >
                      {resolveCellValue(column, item, rowIndex)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
};

export default DataTable;
