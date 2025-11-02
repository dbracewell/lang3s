import type {
  ColumnDef,
  GroupByRenderer,
  SecondaryRowRenderer,
  SortFnType,
  StyleOptions,
} from "@/components/data-table/data-table-types";
import { DataTable } from "@/components/data-table/DataTable";
import { useData } from "@/components/data-table/use-data";
import { useFilters } from "@/components/data-table/use-filters";
import { useSorting } from "@/components/data-table/use-sorting";
import { useMemo } from "react";

export function useDataTable<T extends object>({
  columns,
  data,
  secondaryRowRenderer,
  groupBy,
  groupByRenderer,
  appearance,
  renderFooter = false,
  initialSortColumn,
}: {
  appearance?: StyleOptions;
  columns: ColumnDef<T>[];
  data: T[];
  groupBy?: keyof T;
  groupByRenderer?: GroupByRenderer<T>;
  secondaryRowRenderer?: SecondaryRowRenderer<T>;
  renderFooter?: boolean;
  initialSortColumn?: string;
}) {
  const { getFilter, setFilter, filters } = useFilters<T>();
  const initialSortInfo = useMemo(() => {
    if (initialSortColumn) {
      return (
        columns
          .filter((c) => c.name === initialSortColumn && c.sortFn != null)
          .map((c) => ({
            column: c.name as string,
            sortFn: c.sortFn as SortFnType<T>,
          }))?.[0] ?? undefined
      );
    }
    return undefined;
  }, [initialSortColumn]);

  const { sortColumn, toggleSort, getSortDirection } =
    useSorting<T>(initialSortInfo);

  const { rows, groupedByData } = useData({
    data,
    filters,
    sortColumn,
    columns,
    groupBy,
  });

  const DataTableElement = () => (
    <DataTable.Container className={appearance?.container}>
      <DataTable.Header
        columns={columns}
        className={appearance?.headerRow}
        commonCellClassName={appearance?.headerCell}
        getSortDirection={getSortDirection}
        toggleSort={toggleSort}
        sortButtonClassName={appearance?.sortButton}
      />
      <DataTable.Body className={appearance?.body}>
        {groupedByData
          ? groupedByData.map(([group, groupRows]) => (
              <div key={group}>
                <div className={appearance?.groupByRow}>
                  {groupByRenderer ? (
                    groupByRenderer(group, groupRows)
                  ) : (
                    <>{group}</>
                  )}
                </div>
                {groupRows.map((row, index) => (
                  <DataTable.Row
                    row={row}
                    key={index}
                    columns={columns}
                    commonCellClassName={appearance?.bodyCell}
                    className={appearance?.bodyRow}
                    secondaryRowRenderer={secondaryRowRenderer}
                    secondaryCell={appearance?.secondaryCell}
                    secondaryRow={appearance?.secondaryRow}
                  />
                ))}
              </div>
            ))
          : rows.map((row, index) => (
              <DataTable.Row
                row={row}
                key={index}
                columns={columns}
                commonCellClassName={appearance?.bodyCell}
                className={appearance?.bodyRow}
                secondaryRowRenderer={secondaryRowRenderer}
                secondaryCell={appearance?.secondaryCell}
                secondaryRow={appearance?.secondaryRow}
              />
            ))}
      </DataTable.Body>
      {renderFooter && (
        <DataTable.Footer
          data={rows}
          columns={columns}
          className={appearance?.footerRow}
          commonCellClassName={appearance?.footerRow}
        />
      )}
    </DataTable.Container>
  );

  return {
    toggleSort,
    setFilter,
    DataTable: DataTableElement,
    getFilter,
    rows,
  };
}
