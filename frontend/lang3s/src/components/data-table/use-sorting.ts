import {
  SortFnType,
  SortState,
} from "@/components/data-table/data-table-types";
import { useCallback, useState } from "react";

export const useSorting = <T extends object>(initialSort?: {
  column: string;
  sortFn: SortFnType<T>;
}) => {
  const [sortColumn, setSortColumn] = useState<SortState<T> | undefined>(() =>
    initialSort
      ? {
          ...initialSort,
          dir: "asc",
        }
      : undefined,
  );

  const toggleSort = useCallback(
    (column: string, sortFn: SortFnType<T>) => {
      setSortColumn((prev) => {
        if (prev) {
          const { column: prevColumn, dir } = prev;
          if (prevColumn === column) {
            return {
              ...prev,
              dir: dir === "asc" ? "desc" : "asc",
            };
          }
        }
        return {
          column,
          sortFn,
          dir: "asc",
        };
      });
    },
    [setSortColumn],
  );

  const getSortDirection = useCallback(
    (column: string) => {
      if (sortColumn) {
        const { column: currentColumn, dir } = sortColumn;
        return currentColumn === column ? { dir } : undefined;
      }
      return undefined;
    },
    [sortColumn],
  );

  return { sortColumn, toggleSort, getSortDirection };
};
