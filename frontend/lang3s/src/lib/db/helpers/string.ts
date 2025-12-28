import { sql } from "drizzle-orm";
import { asSQL, CoalesceArgument } from "@/lib/db/helpers/typing";

export const lower = (value: CoalesceArgument<string>) => {
  return sql<string>`LOWER(${asSQL(value)})`;
};

export const upper = (value: CoalesceArgument<string>) => {
  return sql<string>`UPPER(${asSQL(value)})`;
};
