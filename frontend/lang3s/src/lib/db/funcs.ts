import { sql, SQL } from "drizzle-orm";
import { asSQL, CoalesceArgument } from "@/lib/db/helpers/typing";

export * from "./helpers/json";
export * from "./helpers/ordering";
export * from "./helpers/pagination";
export * from "./helpers/string";
export * from "./helpers/vector";

export const coalesce = <T>(...values: CoalesceArgument<T>[]): SQL<T> => {
  if (values.length === 0) {
    throw new Error("coalesce requires at least one argument");
  }
  const sqlChunks = values.map((v) => asSQL(v));
  return sql<T>`coalesce(${sql.join(sqlChunks, sql`, `)})`;
};
