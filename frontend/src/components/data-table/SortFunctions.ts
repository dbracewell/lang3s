import { SortFnType } from "@/components/data-table/data-table-types";

export const StringSort = <T extends object>(
  getter: (row: T) => string,
  caseInsensitive: boolean = true,
): SortFnType<T> => {
  return (a: T, b: T) =>
    caseInsensitive
      ? getter(a).toLowerCase() < getter(b).toLowerCase()
        ? -1
        : 1
      : getter(a) < getter(b)
        ? -1
        : 1;
};
