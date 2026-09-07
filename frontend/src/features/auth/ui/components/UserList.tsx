"use client";
import { useDataTable } from "@/components/data-table/use-data-table";
import { userListColumns, UserType } from "./UserListColumns";
import React from "react";
import DataTableProvider from "@/components/data-table/DataTableContext";
import { AddUserDialog } from "@/features/auth/ui/components/AddUserDialog";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { PageNumbers } from "@/components/PageNumbers";
import { useRouter } from "next/navigation";

export const UserList = ({
  users,
  page,
  totalPages,
}: {
  users: UserType[];
  page: number;
  totalPages: number;
}) => {
  const router = useRouter();
  const { DataTable } = useDataTable({
    columns: userListColumns,
    data: users,
    getRowId: (row) => row.id,
    appearance: {
      container: "flex-1 border bg-card rounded-xl shadow",
      sortButton: "text-white bg-white/30",
      headerRow: "bg-heading text-white text-center",
      headerCell: "p-2",
      bodyCell: "p-1 px-2 h-10 items-center text-sm ",
      bodyRow: "border-b  divide-x bg-row even:bg-alternate-row",
    },
  });

  return (
    <ScrollableBox.Container className="m-1 gap-2">
      <ScrollableBox.Header>
        <h1>Users</h1>
        <p className="pageSubheading">Add and manage system users.</p>
      </ScrollableBox.Header>
      <div className="flex items-center justify-between px-1">
        <AddUserDialog />
      </div>
      <DataTableProvider columns={userListColumns}>
        {DataTable}
      </DataTableProvider>
      <PageNumbers
        totalPages={totalPages}
        currentPage={page}
        pageLink={(to) => router.push(`?page${to}`)}
      />
    </ScrollableBox.Container>
  );
};
