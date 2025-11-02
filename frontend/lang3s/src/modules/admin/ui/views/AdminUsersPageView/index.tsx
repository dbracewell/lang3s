import { UserType } from "@/modules/admin/ui/views/AdminUsersPageView/columns";
import { UserList } from "@/modules/admin/ui/views/AdminUsersPageView/UserList";
import { caller } from "@/trpc/server";

export const AdminUsersPageView = async ({ page }: { page?: string }) => {
  const data = await caller.auth.getUsers();
  return <UserList users={data} />;
};
