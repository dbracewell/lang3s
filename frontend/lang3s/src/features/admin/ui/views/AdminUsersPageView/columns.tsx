import { ColumnDef } from "@/components/data-table/data-table-types";
import { StringSort } from "@/components/data-table/SortFunctions";
import { Checkbox } from "@/components/ui/checkbox";
import { user } from "@/db/schema";
import { DeleteUser } from "@/features/admin/ui/views/AdminUsersPageView/DeleteUser";
import { EditUserDialog } from "@/features/admin/ui/views/AdminUsersPageView/EditUserDialog";
import { UserRole } from "@/features/auth/permissions";

export type UserType = typeof user.$inferSelect & {
  role: UserRole;
};

export const columns: ColumnDef<UserType>[] = [
  {
    name: "name",
    cell: ({ row }) => <>{row.name}</>,
    size: "250px",
    sortFn: StringSort((row) => row.name as string),
  },
  {
    name: "username",
    cell: ({ row }) => <>{row.username}</>,
    size: "250px",
    sortFn: StringSort((row) => row.username as string),
  },
  {
    name: "role",
    cell: ({ row }) => <>{row.role!.toUpperCase()}</>,
    size: "150px",
    align: "center",
    sortFn: StringSort((row) => row.role as string),
  },
  {
    name: "active",
    size: "75px",
    align: "center",
    cell: ({ row }) => (
      <>
        <Checkbox checked={!row.banned} className="cursor-default" />
      </>
    ),
  },
  {
    name: "email",
    cell: ({ row }) => <>{row.email}</>,
    size: "minmax(200px, 1fr)",
    align: "left",
    sortFn: StringSort((row) => row.email as string),
  },
  {
    name: "actions",
    header: "",
    size: "90px",
    cell: ({ row }) => (
      <div className="mx-auto flex items-center gap-2">
        <DeleteUser userId={row.id} />
        <EditUserDialog row={row} />
      </div>
    ),
  },
];
