"use client";
import { useDataTable } from "@/components/data-table/use-data-table";
import { columns, UserType } from "./columns";
import React from "react";
import DataTableProvider from "@/components/data-table/DataTableContext";
import { AddUserDialog } from "@/modules/admin/ui/views/AdminUsersPageView/AddUserDialog";

export const UserList = ({ users }: { users: UserType[] }) => {
  const { DataTable } = useDataTable({
    columns,
    data: users,
    appearance: {
      container: "flex-1 border bg-white rounded-xl shadow",
      sortButton: "text-white bg-white/30",
      headerRow: "bg-dodger-blue-500 text-white text-center",
      headerCell: "p-2",
      bodyCell: "p-1 px-2 h-10 items-center text-sm ",
      bodyRow: "border-b  divide-x even:bg-slate-200",
    },
  });
  return (
    <div className="flex h-full flex-1 flex-col gap-2 overflow-hidden">
      <div className="flex items-center justify-between px-1">
        <AddUserDialog />
      </div>
      <DataTableProvider columns={columns}>
        <DataTable />
      </DataTableProvider>
    </div>
  );
};
