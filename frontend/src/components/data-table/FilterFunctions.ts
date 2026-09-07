import { FilterFnType } from "@/components/data-table/data-table-types";

export const StringCompare = <T extends object>(
  getter: (row: T) => string,
  caseInsensitive: boolean = true,
): FilterFnType<T> => {
  return (row: T, value: unknown) =>
    caseInsensitive
      ? getter(row).toLowerCase() === (value as string).toLowerCase()
      : getter(row) === (value as string);
};

export const StringStartsWith = <T extends object>(
  getter: (row: T) => string,
  caseInsensitive: boolean = true,
): FilterFnType<T> => {
  return (row: T, value: unknown) =>
    caseInsensitive
      ? getter(row)
          .toLowerCase()
          .startsWith((value as string).toLowerCase())
      : getter(row).startsWith(value as string);
};
