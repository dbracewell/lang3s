import { UserInfo } from "@/modules/auth/shared_types";
import React from "react";

export const AdminPageView = ({ user }: { user: UserInfo }) => {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col bg-red-500">
      {user.username}
    </div>
  );
};
