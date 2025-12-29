import { requireAdmin } from "@/features/auth/server/actions";
import React from "react";

const AdminPage = async () => {
  const user = await requireAdmin();
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col bg-red-500">
      {user.username}
    </div>
  );
};

export default AdminPage;
