import React from "react";
import { BasicUserInfo } from "@/features/common/types";

export const AdminPageView = ({ user }: { user: BasicUserInfo }) => {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col bg-red-500">
      {user.username}
    </div>
  );
};
