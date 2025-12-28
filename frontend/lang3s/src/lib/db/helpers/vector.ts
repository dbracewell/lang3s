import { Column, sql, SQL } from "drizzle-orm";
import { CoalesceArgument } from "@/lib/db/helpers/typing";

export function cosineSimilarity(
  column: CoalesceArgument<number[]>,
  vector: number[] | string[] | Column | SQL.Aliased<number[]>,
) {
  if (vector instanceof Column || vector instanceof SQL.Aliased) {
    return sql`(1 - cosine_distance(${column},${vector}::halfvec)::float)`;
  }
  return sql`(1 - cosine_distance(${column},${JSON.stringify(vector)}::halfvec)::float)`;
}
