// 2. Define a generic type for any Drizzle query that supports pagination
//    This allows it to work with PgSelect, MySqlSelect, and SQLiteSelect.
import { PAGE_LIMIT } from "@/features/common/constants";

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
