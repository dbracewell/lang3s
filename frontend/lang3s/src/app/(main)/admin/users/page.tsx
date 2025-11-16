import { AdminUsersPageView } from "@/features/admin/ui/views/AdminUsersPageView";
import { requireAdmin } from "@/features/auth/server/actions";

const AdminUsersPage = async (props: PageProps<"/admin/users">) => {
  await requireAdmin();
  const query = await props.searchParams;
  const page = (query?.page as string) ?? undefined;
  return <AdminUsersPageView page={page} />;
};

export default AdminUsersPage;
