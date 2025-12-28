import { sql } from "drizzle-orm";
import { OntologyTable } from "@/lib/db/schema";

export const createPathWildcards = (values: string[]) => {
  return sql.join(
    values.flatMap((v) => [v, `${v}.*`]).map((v) => sql`${v}`),
    sql`, `,
  );
};

export const matchPath = (
  table: { path: string } | typeof OntologyTable,
  values: string[],
) => {
  return sql`${table.path} ~ any(array[${createPathWildcards(values)}]::lquery[])`;
};
