import { caller } from "@/lib/trpc/server";
import React from "react";
import { AccountHeader } from "@/features/auth/ui/components/AccountHeader";
import { UserInformation } from "@/features/auth/ui/components/UserInformation";
import { UserProjects } from "@/features/auth/ui/components/UserProjects";
import { UserApiKeys } from "@/features/auth/ui/components/UserApiKeys";

const UserPage = async () => {
  const user = await caller.auth.getAccount();
  return (
    <div className="flex h-full flex-1 flex-col gap-5 overflow-hidden p-2">
      <AccountHeader user={user} />
      <UserInformation user={user} />
      <div className="scrollable bg-card flex min-h-0 flex-1 flex-col gap-6">
        <UserProjects user={user} />
        <UserApiKeys user={user} />
      </div>
    </div>
  );
};

export default UserPage;
