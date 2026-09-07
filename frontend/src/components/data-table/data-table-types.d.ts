export type StyleOptions = {
  sortButton?: string;
  container?: string;
  headerRow?: string;
  headerCell?: string;
  bodyRow?: string;
  bodyCell?: string;
  groupByRow?: string;
  secondaryRow?: string;
  secondaryCell?: string;
  footerRow?: string;
  footerCell?: string;
  body?: string;
};

export type SortFnType<T extends Object> = (a: T, b: T) => number;
export type FilterFnType<T extends Object> = (
  row: T,
  filter: unknown,
) => boolean;

type SortState<T extends object> = {
  column: string;
  sortFn: SortFnType<T>;
  dir: "asc" | "desc";
};

export type FilterState<T extends Object> = {
  column: string;
  value?: unknown;
};

export type GroupByRenderer<T extends object> = (
  key: string,
  rows: T[],
) => React.ReactNode;

export type SecondaryRowRenderer<T extends object> = (
  row: T,
) => React.ReactNode;

type _ColumnDef<T extends object, K extends keyof T = keyof T> = {
  name: string;

  header?: string | React.ReactNode;
  headerClassName?: string;

  cell: ({ row }: { row: T }) => React.ReactNode;
  cellClassName?: string;

  size: string;
  align?: "center" | "left" | "right";

  sortFn?: SortFnType<T>;
  filterFn?: FilterFnType<T>;

  footer?: {
    className?: string;
    cell: (data: T[]) => React.ReactNode;
  };
};

export type ColumnDef<T extends object> = {
  [K in keyof T]-?: _ColumnDef<T, K>;
}[keyof T];
