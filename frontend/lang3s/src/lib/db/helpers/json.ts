import { Column, sql, SQL, SQLWrapper } from "drizzle-orm";
import { asSQL, InferValue } from "@/lib/db/helpers/typing";
import { CHAT_HISTORY_STORAGE_KEY } from "@/features/chat/constants";

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

export function jsonStrictAgg<T>(
  value: T,
  orderExpr?: SQL<unknown>,
  jsonb: boolean = false,
): SQL<InferValue<T>[]> {
  const valSql = asSQL(value);
  if (orderExpr == null) {
    if (jsonb) {
      return sql<InferValue<T>[]>`jsonb_agg_strict(${valSql})`;
    }
    return sql<InferValue<T>[]>`json_agg_strict(${valSql})`;
  }
  if (jsonb) {
    sql<InferValue<T>[]>`jsonb_agg_strict(${valSql} order by ${orderExpr})`;
  }
  return sql<InferValue<T>[]>`json_agg_strict(${valSql} order by ${orderExpr})`;
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

export const jsonValue = <T>(
  column: Column | SQLWrapper,
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
    | "string[]"
    | "number"
    | "int[]"
    | "float[]"
    | "json" = "text",
) => {
  switch (castAs) {
    case "string":
    case "text":
      return sql<T>`(${column}->>${key})::text`;
    case "text[]":
    case "string[]":
      return sql<T>`(${column}->>${key})::text[]`;
    case "int":
    case "float":
    case "number":
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
