import { AdminUsersPageView } from "@/features/auth/ui/views/AdminUsersPageView";
import { requireAdmin } from "@/features/auth/server/actions";
import { caller } from "@/lib/trpc/server";
import { UserList } from "@/features/auth/ui/components/UserList";

const AdminUsersPage = async (props: PageProps<"/admin/users">) => {
  await requireAdmin();
  const query = await props.searchParams;
  const page = (query?.page as string) ?? undefined;
  const data = await caller.auth.getUsers();
  return <UserList users={data} />;
};

export default AdminUsersPage;
