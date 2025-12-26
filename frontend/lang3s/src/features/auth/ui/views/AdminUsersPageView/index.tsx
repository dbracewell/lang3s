import { UserList } from "@/features/auth/ui/views/AdminUsersPageView/UserList";
import { caller } from "@/lib/trpc/server";

export const AdminUsersPageView = async ({ page }: { page?: string }) => {
  const data = await caller.auth.getUsers();
  return <UserList users={data} />;
};
