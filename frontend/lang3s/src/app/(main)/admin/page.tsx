import { AdminPageView } from "@/modules/admin/ui/views/AdminPageView";
import { requireAdmin } from "@/modules/auth/server/actions";

const AdminPage = async () => {
  const user = await requireAdmin();
  return <AdminPageView user={user} />;
};

export default AdminPage;
