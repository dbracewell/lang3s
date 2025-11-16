import { AdminPageView } from "@/features/admin/ui/views/AdminPageView";
import { requireAdmin } from "@/features/auth/server/actions";

const AdminPage = async () => {
  const user = await requireAdmin();
  return <AdminPageView user={user} />;
};

export default AdminPage;
