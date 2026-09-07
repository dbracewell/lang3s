import type {
  ColumnDef,
  FilterState,
  SortState,
} from "@/components/data-table/data-table-types";
import { doGroupBy } from "@/components/data-table/data-table-utils";
import { useDebounce } from "@/hooks/useDebounce";
import { useMemo } from "react";

export const useData = <T extends object, K extends keyof T = keyof T>({
  data,
  filters,
  sortColumn,
  columns,
  groupBy,
}: {
  data: T[];
  filters?: Record<string, FilterState<T>>;
  sortColumn?: SortState<T>;
  columns: ColumnDef<T>[];
  groupBy?: K;
}) => {
  const debouncedFilters = useDebounce(filters, 300);
  const rows = useMemo(() => {
    let rows = data.map((row) => ({ ...row }));

    if (debouncedFilters) {
      const activeFilters = columns
        .map((c) => {
          if (!c.filterFn || debouncedFilters[c.name] == null) {
            return null;
          }
          return {
            ...debouncedFilters[c.name],
            filterFn: c.filterFn,
          };
        })
        .filter((f) => f != null);

      if (activeFilters.length > 0) {
        rows = rows.filter((row) => {
          for (const { filterFn, value } of activeFilters) {
            if (!filterFn(row, value)) {
              return false;
            }
          }
          return true;
        });
      }
    }

    if (sortColumn) {
      return rows.sort((a, b) => {
        const sortDirection = sortColumn.dir;
        const order = sortColumn.sortFn(a, b);
        if (sortDirection === "asc") {
          return order;
        }
        return -order;
      });
    }

    return rows;
  }, [data, sortColumn, columns, debouncedFilters]);

  const groupedByData = useMemo(() => {
    if (groupBy) {
      return doGroupBy(rows, groupBy);
    }
    return undefined;
  }, [groupBy, rows]);

  return { rows, groupedByData };
};
