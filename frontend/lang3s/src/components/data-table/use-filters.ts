import { FilterState } from "@/components/data-table/data-table-types";
import { omitFields } from "@/lib/utils/type-utils";
import { useCallback, useState } from "react";

export const useFilters = <T extends object>() => {
  const [filters, setFilters] = useState<Record<string, FilterState<T>>>();

  const setFilter = useCallback(
    (state: FilterState<T>) => {
      if (state.value == null) {
        setFilters((prev) =>
          prev ? omitFields(prev ?? {}, [state.column]) : undefined,
        );
      } else {
        setFilters((prev) => ({
          ...prev,
          [state.column]: state,
        }));
      }
    },
    [setFilters],
  );

  const getFilter = useCallback(
    (key: string) => {
      if (filters) {
        return filters[key];
      }
      return undefined;
    },
    [filters],
  );

  return { filters, getFilter, setFilter };
};
