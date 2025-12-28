import { getTableColumns, Table } from "drizzle-orm";
import { PickColumns } from "@/lib/db/helpers/typing";

export function selectFields<
  T extends Table,
  K extends keyof T["_"]["columns"],
>(table: T, fields: K[]): PickColumns<T, K> {
  const allColumns = getTableColumns(table);
  const result = {} as any;

  fields.forEach((key) => {
    if (allColumns[key as string]) {
      result[key] = allColumns[key as string];
    }
  });

  return result as PickColumns<T, K>;
}
