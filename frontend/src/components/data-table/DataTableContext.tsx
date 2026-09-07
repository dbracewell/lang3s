"use client";
import { ColumnDef } from "@/components/data-table/data-table-types";
import React, { createContext, RefObject, useMemo, useRef } from "react";

export const DataTableContext = createContext<{
  gridTemplateColumns: string;
  bodyRef: RefObject<HTMLDivElement | null> | null;
  headerRef: RefObject<HTMLDivElement | null> | null;
  scrollPosition: RefObject<number> | null;
  context: Record<string, unknown>;
}>({
  gridTemplateColumns: "",
  bodyRef: null,
  headerRef: null,
  scrollPosition: null,
  context: {},
});

export const useDataTableContext = () => {
  return React.useContext(DataTableContext);
};

export const DataTableProvider = <T extends object>({
  columns,
  children,
  context,
}: {
  columns: ColumnDef<T>[];
  children: React.ReactNode;
  context?: Record<string, unknown>;
}) => {
  const gridTemplateColumns = useMemo(
    () => columns.map((c) => c.size).join(" "),
    [columns],
  );
  const headerRef = useRef<HTMLDivElement | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const scrollPosition = useRef(0);

  const contextValue = useMemo(
    () => ({
      gridTemplateColumns,
      bodyRef,
      headerRef,
      scrollPosition,
      context: context ?? {},
    }),
    [context, gridTemplateColumns],
  );

  return (
    <DataTableContext.Provider value={contextValue}>
      {children}
    </DataTableContext.Provider>
  );
};

export default DataTableProvider;
