import { AnyColumn, isSQLWrapper, sql, SQL, type Table } from "drizzle-orm";

export type PickColumns<T extends Table, K extends keyof T["_"]["columns"]> = {
  [P in K]: T["_"]["columns"][P];
};

export type CoalesceArgument<T> =
  | T
  | SQL<T>
  | SQL.Aliased<T>
  | AnyColumn<{ data: T }>;

export type InferValue<T> =
  // 1. Handle SQL<T> (Raw SQL chunks)
  T extends SQL<infer U>
    ? U
    : // 2. NEW: Handle Aliased Values (.as("name"))
      T extends SQL.Aliased<infer U>
      ? U
      : // 3. Handle Drizzle Columns (Table.column)
        T extends AnyColumn
        ? T["_"]["data"]
        : // 4. Handle things with .getSQL() (Subqueries, etc.)
          T extends { getSQL: () => SQL<infer U> }
          ? U
          : // 5. Primitives
            T;

const hasGetSQL = (x: any): x is { getSQL: () => SQL<any> } => {
  return x != null && typeof x.getSQL === "function";
};

export const asSQL = <T>(value: T): SQL<T> => {
  if (value instanceof SQL || isSQLWrapper(value)) {
    return sql`${value}`;
  }
  if (hasGetSQL(value)) {
    return value.getSQL();
  }
  return sql`${value}`;
};
