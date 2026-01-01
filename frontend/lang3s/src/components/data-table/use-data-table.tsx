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
import { memo, useEffect, useMemo, useRef } from "react";
import { redirect } from "next/navigation";

export function useDataTable<T extends object>({
  columns,
  data,
  getRowId,
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
  getRowId: (row: T) => string;
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
  }, [initialSortColumn, columns]);

  const { sortColumn, toggleSort } = useSorting<T>(initialSortInfo);

  const { rows, groupedByData } = useData({
    data,
    filters,
    sortColumn,
    columns,
    groupBy,
  });

  return {
    toggleSort,
    setFilter,
    DataTable: (
      <DataTableElement
        appearance={appearance}
        columns={columns}
        rows={rows}
        getRowId={getRowId}
        groupedByData={groupedByData}
        renderFooter={renderFooter}
        groupByRenderer={groupByRenderer}
        initialSortColumn={initialSortColumn}
        secondaryRowRenderer={secondaryRowRenderer}
      />
    ),
    getFilter,
    rows,
  };
}

const DataTableElement = <T extends Object>({
  columns,
  rows,
  groupedByData,
  getRowId,
  secondaryRowRenderer,
  groupByRenderer,
  appearance,
  renderFooter = false,
  initialSortColumn,
}: {
  appearance?: StyleOptions;
  columns: ColumnDef<T>[];
  rows: T[];
  groupedByData: [string, T[]][] | undefined;
  getRowId: (row: T) => string;
  groupByRenderer?: GroupByRenderer<T>;
  secondaryRowRenderer?: SecondaryRowRenderer<T>;
  renderFooter?: boolean;
  initialSortColumn?: string;
}) => {
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
  }, [initialSortColumn, columns]);
  const { sortColumn, toggleSort, getSortDirection } =
    useSorting<T>(initialSortInfo);
  return (
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
          : rows.map((row) => (
              <DataTable.Row
                row={row}
                key={getRowId(row)}
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
};
