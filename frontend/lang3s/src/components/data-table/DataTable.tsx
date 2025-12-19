import {
  ColumnDef,
  SecondaryRowRenderer,
  SortFnType,
} from "@/components/data-table/data-table-types";
import { useDataTableContext } from "@/components/data-table/DataTableContext";
import { capitalize } from "@/lib/utils/formatters";
import { cn } from "@/lib/utils/cn";
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react";
import React, { useEffect } from "react";

type DataTableContainerProps = {
  className?: string;
  children: React.ReactNode;
};

const DataTableContainer = ({
  children,
  className,
}: DataTableContainerProps) => {
  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col overflow-y-hidden",
        className,
      )}
    >
      {children}
    </div>
  );
};

type DataTableHeaderProps<T extends object> = {
  commonCellClassName?: string;
  sortButtonClassName?: string;
  className?: string;
  columns: ColumnDef<T>[];
  toggleSort: (column: string, sortFn: SortFnType<T>) => void;
  getSortDirection: (column: string) => { dir: "asc" | "desc" } | undefined;
};

const DataTableHeader = <T extends Object>({
  commonCellClassName,
  sortButtonClassName,
  className,
  columns,
  toggleSort,
  getSortDirection,
}: DataTableHeaderProps<T>) => {
  const { gridTemplateColumns, bodyRef, headerRef } = useDataTableContext();

  const padding =
    bodyRef?.current &&
    bodyRef.current.scrollHeight > bodyRef.current.clientHeight
      ? bodyRef.current.offsetWidth - bodyRef.current.clientWidth
      : 0;

  return (
    <div
      className={cn("hide-scrollbar grid overflow-x-auto", className)}
      ref={headerRef}
      style={{
        gridTemplateColumns,
        paddingRight: `${padding}px`,
      }}
    >
      {columns.map((c, i) => {
        const sortDirection = getSortDirection(c.name)?.dir;
        const isSorted = !!sortDirection;
        return (
          <div
            className={cn(
              "flex items-center font-semibold",
              commonCellClassName,
              c.headerClassName,
              c.align === "center" && "justify-center!",
              c.align === "right" && "justify-end!",
              c.align === "left" && "justify-start!",
            )}
            key={`column-${i}`}
          >
            {c.header ?? capitalize(c.name)}
            {c.sortFn != null && (
              <button
                onClick={() => toggleSort(c.name, c.sortFn!)}
                type="button"
                className={cn(
                  "text-foreground ml-2 flex size-4 items-center justify-center rounded-full [&>_svg]:size-4",
                  sortButtonClassName,
                  !isSorted && "opacity-0 transition-all hover:opacity-100",
                )}
              >
                {sortDirection !== "desc" && <ArrowDownIcon />}
                {sortDirection === "desc" && <ArrowUpIcon />}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
};

type DataTableBodyProps = {
  className?: string;
  children: React.ReactNode;
};

const DataTableBody = ({ className, children }: DataTableBodyProps) => {
  const { bodyRef, scrollPosition, headerRef } = useDataTableContext();

  useEffect(() => {
    const el = bodyRef?.current;
    if (!el) return;
    if (!scrollPosition) return;
    el.scrollTop = scrollPosition.current;
    if (headerRef?.current) {
      headerRef.current.scrollLeft = el.scrollLeft;
    }
  }, []);

  return (
    <div
      ref={bodyRef}
      className={cn("scrollable flex-1", className)}
      onScroll={() => {
        const el = bodyRef?.current;
        if (!el) return;
        if (!scrollPosition) return;
        scrollPosition.current = el.scrollTop;
        if (headerRef?.current) {
          headerRef.current.scrollLeft = el.scrollLeft;
        }
      }}
    >
      {children}
    </div>
  );
};

type DataTableRowProps<T extends object> = {
  className?: string;
  commonCellClassName?: string;
  columns: ColumnDef<T>[];
  row: T;
  secondaryRowRenderer?: SecondaryRowRenderer<T>;
  secondaryRow?: string;
  secondaryCell?: string;
};
const DataTableRow = <T extends Object>({
  className,
  row,
  columns,
  commonCellClassName,
  secondaryRowRenderer,
  secondaryRow,
  secondaryCell,
}: DataTableRowProps<T>) => {
  const { gridTemplateColumns } = useDataTableContext();
  return (
    <div
      className={cn(
        "grid min-w-full items-center justify-items-center",
        className,
      )}
      style={{
        display: "inline-grid",
        gridTemplateColumns,
      }}
    >
      {columns.map((c, i) => (
        <div
          className={cn(
            "flex h-full w-full overflow-hidden",
            c.align === "center" && "justify-center!",
            c.align === "right" && "justify-end!",
            c.align === "left" && "justify-start!",
            commonCellClassName,
            c.cellClassName,
          )}
          key={`column-${i}`}
        >
          {c.cell({ row })}
        </div>
      ))}
      {secondaryRowRenderer && (
        <div
          className={cn(
            "flex h-full w-full items-center overflow-hidden p-4",
            secondaryRow,
          )}
          style={{
            gridColumn: `1 / ${columns.length + 1}`,
          }}
        >
          <div className={secondaryCell}>{secondaryRowRenderer(row)}</div>
        </div>
      )}
    </div>
  );
};

type DataTableFooterProps<T extends object> = {
  className?: string;
  commonCellClassName?: string;
  columns: ColumnDef<T>[];
  data: T[];
};

const DataTableFooter = <T extends Object>({
  className,
  columns,
  commonCellClassName,
  data,
}: DataTableFooterProps<T>) => {
  const { gridTemplateColumns } = useDataTableContext();
  return (
    <div
      className={cn("grid items-center justify-items-center", className)}
      style={{
        gridTemplateColumns,
      }}
    >
      {columns.map((c, i) => (
        <div
          className={cn(
            "flex h-full w-full overflow-hidden",
            commonCellClassName,
            c.footer?.className,
          )}
          key={`column-${i}`}
        >
          {c.footer?.cell(data) ?? <></>}
        </div>
      ))}
    </div>
  );
};

function typedMemo<T extends Object>(component: T): T {
  return React.memo(component as any) as any;
}

export const DataTable = {
  Container: typedMemo(DataTableContainer),
  Header: typedMemo(DataTableHeader),
  Body: typedMemo(DataTableBody),
  Row: typedMemo(DataTableRow),
  Footer: typedMemo(DataTableFooter),
};
