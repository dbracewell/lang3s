import { type AnyColumn, sql, SQL } from "drizzle-orm";
import { asSQL } from "@/lib/db/helpers/typing";

export const orderAsc = <T>(col: AnyColumn | SQL<T> | SQL.Aliased<any>) =>
  sql`${asSQL(col)} ASC`;

export const orderDesc = <T>(col: AnyColumn | SQL<T> | SQL.Aliased<any>) =>
  sql`${asSQL(col)} DESC`;
