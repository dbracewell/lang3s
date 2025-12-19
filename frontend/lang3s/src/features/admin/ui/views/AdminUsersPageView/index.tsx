import { UserType } from "@/features/admin/ui/views/AdminUsersPageView/columns";
import { UserList } from "@/features/admin/ui/views/AdminUsersPageView/UserList";
import { caller } from "@/lib/trpc/server";

export const AdminUsersPageView = async ({ page }: { page?: string }) => {
  const data = await caller.auth.getUsers();
  return <UserList users={data} />;
};
