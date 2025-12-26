import { AnyColumn, Column, isSQLWrapper, sql, SQL, Subquery } from "drizzle-orm";
import { PAGE_LIMIT } from "@/features/common/constants";
import Aliased = SQL.Aliased;

export function getSubqueryColumns<
  TAlias extends string,
  TSelection extends Record<string, unknown>,
>(sq: Subquery<TAlias, TSelection>): TSelection {
  const fields =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (sq as any)?._.selectedFields ??
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (sq as any)?._.selection ?? // some versions
    undefined;

  if (!fields || typeof fields !== "object") {
    throw new Error(
      "subquerySelection: could not find selected fields. Make sure you used select({ ... }) before .as('alias').",
    );
  }

  return { ...fields } as TSelection;
}

type CoalesceArgument<T> = T | SQL<T> | Aliased<T> | AnyColumn<{ data: T }>;

type InferValue<T> =
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

const asSQL = <T>(value: T): SQL<T> => {
  if (value instanceof SQL || isSQLWrapper(value)) {
    return sql`${value}`;
  }
  if (hasGetSQL(value)) {
    return value.getSQL();
  }
  return sql`${value}`;
};

export function jsonBuildObject<T extends Record<string, any>>(
  obj: T,
  jsonb: boolean = false,
): SQL<{ [K in keyof T]: InferValue<T[K]> }> {
  const parts: SQL[] = [];

  for (const [key, value] of Object.entries(obj)) {
    const keySql = sql.raw(`'${key.replace(/'/g, "''")}'`);
    const valSql = asSQL(value);
    parts.push(keySql, valSql);
  }

  if (jsonb) {
    return sql<{ [K in keyof T]: InferValue<T[K]> }>`
    jsonb_build_object(${sql.join(parts, sql`, `)})
  `;
  }
  return sql<{ [K in keyof T]: InferValue<T[K]> }>`
    json_build_object(${sql.join(parts, sql`, `)})
  `;
}

export const orderAsc = <T>(col: AnyColumn | SQL<T> | Aliased<any>) =>
  sql`${asSQL(col)} ASC`;

export const orderDesc = <T>(col: AnyColumn | SQL<T> | Aliased<any>) =>
  sql`${asSQL(col)} DESC`;

export function jsonAgg<T>(
  value: T,
  orderExpr?: SQL<unknown>,
  jsonb: boolean = false,
): SQL<InferValue<T>[]> {
  const valSql = asSQL(value);
  if (orderExpr == null) {
    if (jsonb) {
      return sql<InferValue<T>[]>`jsonb_agg(${valSql})`;
    }
    return sql<InferValue<T>[]>`json_agg(${valSql})`;
  }
  if (jsonb) {
    sql<InferValue<T>[]>`jsonb_agg(${valSql} order by ${orderExpr})`;
  }
  return sql<InferValue<T>[]>`json_agg(${valSql} order by ${orderExpr})`;
}

export function jsonbBuildObject<T extends Record<string, any>>(
  obj: T,
): SQL<{ [K in keyof T]: InferValue<T[K]> }> {
  const parts: SQL[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const keySql = sql.raw(`'${key.replace(/'/g, "''")}'`);
    const valSql = asSQL(value);
    parts.push(keySql, valSql);
  }
  return sql<{ [K in keyof T]: InferValue<T[K]> }>`
    jsonb_build_object(${sql.join(parts, sql`, `)})
  `;
}

export function jsonbAgg<T>(
  value: T,
  orderExpr?: SQL<any>,
): SQL<InferValue<T>[]> {
  const valSql = asSQL(value);
  if (orderExpr == null) {
    return sql<InferValue<T>[]>`jsonb_agg(${valSql})`;
  }
  return sql<InferValue<T>[]>`jsonb_agg(${valSql} order by ${orderExpr})`;
}

export function cosineSimilarity(
  column: CoalesceArgument<number[]>,
  vector: number[] | string[] | Column,
) {
  if (vector instanceof Column) {
    return sql`(1 - cosine_distance(${column},${vector}::halfvec)::float)`;
  }
  return sql`(1 - cosine_distance(${column},${JSON.stringify(vector)}::halfvec)::float)`;
}

export function pgroonga_score() {
  return sql<number>`pgroonga_score(tableoid,ctid)`;
}

export function pgroonga_query(
  column: CoalesceArgument<string>,
  query: string,
  index: string,
) {
  return sql`${column} &@~  (${query}, 
																ARRAY[1],
 																ARRAY['scorer_tf_idf($index)'],
 																${index})::pgroonga_full_text_search_condition_with_scorers`;
}

// 2. Define a generic type for any Drizzle query that supports pagination
//    This allows it to work with PgSelect, MySqlSelect, and SQLiteSelect.
interface Partitionable {
  limit: (limit: number) => any;
  offset: (offset: number) => any;
}

export function withPagination<T extends Partitionable>(
  qb: T,
  options?: {
    page?: number;
    pageSize?: number;
  },
): T {
  const { page = 1, pageSize = PAGE_LIMIT } = options ?? {};
  const offset = Math.max(1, page);
  const safePageSize = Math.max(1, pageSize);
  return qb.limit(safePageSize + 1).offset((offset - 1) * safePageSize) as T;
}

export function generateNextPage<T>(results: T[], pageLimit?: number) {
  const safePageLimit = pageLimit ? pageLimit : PAGE_LIMIT;
  const hasNextPage = results.length > safePageLimit;
  const finalResults = hasNextPage
    ? results.slice(0, results.length - 1)
    : results;
  return { hasNextPage, finalResults };
}

export const lower = (value: CoalesceArgument<string>) => {
  return sql<string>`LOWER(${asSQL(value)})`;
};

export const upper = (value: CoalesceArgument<string>) => {
  return sql<string>`UPPER(${asSQL(value)})`;
};

export const coalesce = <T>(...values: CoalesceArgument<T>[]): SQL<T> => {
  if (values.length === 0) {
    throw new Error("coalesce requires at least one argument");
  }
  const sqlChunks = values.map((v) => asSQL(v));
  return sql<T>`coalesce(${sql.join(sqlChunks, sql`, `)})`;
};

export const jsonValue = <T>(
  column: Column,
  key: string,
  castAs:
    | "text"
    | "string"
    | "date"
    | "datetime"
    | "int"
    | "float"
    | "boolean"
    | "text[]"
    | "int[]"
    | "float[]"
    | "json" = "text",
) => {
  switch (castAs) {
    case "string":
    case "text":
      return sql<T>`(${column}->>${key})::text`;
    case "text[]":
      return sql<T>`(${column}->>${key})::text[]`;
    case "int":
    case "float":
      return sql<T>`(${column}->>${key})::numeric`;
    case "int[]":
    case "float[]":
      return sql<T>`(${column}->>${key})::numeric[]`;
    case "json":
      return sql<T>`(${column}->${key})`;
    case "boolean":
      return sql<T>`(${column}->>${key})::boolean`;
    case "date":
    case "datetime":
      return sql<T>`(${column}->>${key})::timestamp`;
  }
};
