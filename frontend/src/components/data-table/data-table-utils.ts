export function doGroupBy<T extends object, K extends keyof T>(
  array: T[],
  key: K,
): [string, T[]][] {
  return Object.entries(
    array.reduce(
      (acc, item) => {
        const groupKey = String(item[key]);
        if (!acc[groupKey]) {
          acc[groupKey] = [];
        }
        acc[groupKey].push(item);
        return acc;
      },
      {} as Record<string, T[]>,
    ),
  );
}
