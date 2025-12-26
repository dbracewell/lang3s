import { AdminPageView } from "@/features/auth/ui/views/AdminPageView";
import { requireAdmin } from "@/features/auth/server/actions";

const AdminPage = async () => {
  const user = await requireAdmin();
  return <AdminPageView user={user} />;
};

export default AdminPage;
