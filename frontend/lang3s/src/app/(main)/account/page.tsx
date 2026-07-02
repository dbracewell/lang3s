import React from "react";
import { AccountHeader } from "@/features/auth/ui/components/AccountHeader";
import { UserInformation } from "@/features/auth/ui/components/UserInformation";
import {
  getCurrentUser,
  roleHasPermissions,
} from "@/features/auth/server/actions";
import { UserRole } from "@/lib/auth/permissions";
import { UserProjects } from "@/features/auth/ui/components/UserProjects";
import { UserApiKeys } from "@/features/auth/ui/components/UserApiKeys";
import { redirect } from "next/navigation";

const UserPage = async () => {
  const user = await getCurrentUser();
  const hasApiPermission = await roleHasPermissions(user.role as UserRole, [
    "data:load",
    "model:create",
  ]);
  if (!hasApiPermission) {
    throw redirect("/");
  }
  return (
    <div className="m-1 flex h-full flex-1 flex-col gap-5 overflow-hidden p-2">
      <AccountHeader user={user} />
      <UserInformation user={user} />
      <div className="scrollable bg-card flex min-h-0 flex-1 flex-col gap-6">
        <UserProjects user={user} />
        {hasApiPermission && <UserApiKeys user={user} />}
      </div>
    </div>
  );
};

export default UserPage;
