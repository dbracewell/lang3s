// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function doGroupBy<T extends Record<string, any>, K extends keyof T>(
  array: T[],
  key: K,
): [string, T[]][] {
  return Object.entries(
    array.reduce(
      (acc, item) => {
        const groupKey = item[key];
        if (!acc[groupKey]) {
          acc[groupKey] = [];
        }
        acc[groupKey].push(item);
        return acc;
      },
      {} as Record<T[K], T[]>,
    ),
  );
}
