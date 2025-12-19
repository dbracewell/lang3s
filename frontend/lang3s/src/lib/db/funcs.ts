import { AnyColumn, Column, isSQLWrapper, sql, SQL, SQLWrapper } from "drizzle-orm";
import { TypedQueryBuilder } from "drizzle-orm/query-builders/query-builder";
import { PAGE_LIMIT } from "@/features/common/constants";
import Aliased = SQL.Aliased;

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

function hasGetSQL(x: any): x is { getSQL: () => SQL<any> } {
  return x != null && typeof x.getSQL === "function";
}

/**
 * Normalize any supported value into a SQL expression.
 */
function toSql(value: any): SQL {
  if (value instanceof SQL || isSQLWrapper(value)) {
    return sql`${value}`;
  }

  // This is the missing piece: Check for Drizzle Columns
  if (
    value instanceof Column ||
    (typeof value === "object" && value !== null && "_isDrizzleColumn" in value)
  ) {
    return sql`${value}`;
  }

  // Handle primitives (strings, numbers, booleans)
  return sql`${value}`;
}

export function jsonBuildObject<T extends Record<string, any>>(
  obj: T,
): SQL<{ [K in keyof T]: InferValue<T[K]> }> {
  const parts: SQL[] = [];

  for (const [key, value] of Object.entries(obj)) {
    const keySql = sql.raw(`'${key.replace(/'/g, "''")}'`);
    const valSql = toSql(value);
    parts.push(keySql, valSql);
  }

  return sql<{ [K in keyof T]: InferValue<T[K]> }>`
    json_build_object(${sql.join(parts, sql`, `)})
  `;
}

export const orderAsc = <T>(col: AnyColumn | SQL<T> | Aliased<any>) =>
  sql`${toSql(col)} ASC`;

export const orderDesc = <T>(col: AnyColumn | SQL<T> | Aliased<any>) =>
  sql`${toSql(col)} DESC`;

export function jsonAgg<T>(
  value: T,
  orderExpr?: SQL<any>,
): SQL<InferValue<T>[]> {
  let valSql: SQL;

  if (value instanceof SQL) {
    valSql = value;
  } else if (hasGetSQL(value)) {
    valSql = value.getSQL();
  } else if (
    value &&
    typeof value === "object" &&
    "_isDrizzleColumn" in value
  ) {
    valSql = sql`${value}`;
  } else {
    valSql = sql`${value}`;
  }

  if (orderExpr == null) {
    return sql<InferValue<T>[]>`json_agg(${valSql})`;
  }

  return sql<InferValue<T>[]>`json_agg(${valSql} order by ${orderExpr})`;
}

export function jsonbBuildObject<T extends Record<string, any>>(
  obj: T,
): SQL<{ [K in keyof T]: InferValue<T[K]> }> {
  const parts: SQL[] = [];

  for (const [key, value] of Object.entries(obj)) {
    const keySql = sql.raw(`'${key.replace(/'/g, "''")}'`);
    const valSql = toSql(value);
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
  let valSql: SQL;

  if (value instanceof SQL) {
    valSql = value;
  } else if (hasGetSQL(value)) {
    valSql = value.getSQL();
  } else if (
    value &&
    typeof value === "object" &&
    "_isDrizzleColumn" in value
  ) {
    valSql = sql`${value}`;
  } else {
    valSql = sql`${value}`;
  }

  if (orderExpr == null) {
    return sql<InferValue<T>[]>`jsonb_agg(${valSql})`;
  }

  return sql<InferValue<T>[]>`jsonb_agg(${valSql} order by ${orderExpr})`;
}

export function cosineSimilarity(
  column: SQLWrapper | AnyColumn,
  vector: number[] | string[] | TypedQueryBuilder<any> | string,
) {
  return sql`(1 - cosine_distance(${column},${JSON.stringify(vector)}::halfvec)::float)`;
}

export function pgroonga_score() {
  return sql`pgroonga_score(tableoid,ctid)`;
}

export function pgroonga_query(column: AnyColumn | SQLWrapper, query: string) {
  return sql`${column} &@~  (${query}, 
																ARRAY[1],
 																ARRAY['scorer_tf_idf($index)'],
 																'ml_text_search_index')::pgroonga_full_text_search_condition_with_scorers`;
}

export interface PaginationOptions {
  page?: number;
  pageSize?: number;
}

// 2. Define a generic type for any Drizzle query that supports pagination
//    This allows it to work with PgSelect, MySqlSelect, and SQLiteSelect.
interface Partitionable {
  limit: (limit: number) => any;
  offset: (offset: number) => any;
}

export function withPagination<T extends Partitionable>(
  qb: T,
  options: PaginationOptions,
): T {
  const { page = 1, pageSize = PAGE_LIMIT } = options;
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
