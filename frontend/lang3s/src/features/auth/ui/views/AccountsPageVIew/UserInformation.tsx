import { FullUserInfo } from "@/features/common/types";
import React from "react";

export const UserInformation = ({ user }: { user: FullUserInfo }) => {
  return (
    <div className="flex w-fit min-w-[300px] flex-col gap-2 divide-y rounded-lg border bg-slate-100 p-2 dark:bg-slate-900">
      <div className="flex items-center gap-3 p-2">
        <span className="font-semibold">Name:</span>
        <span>{user.name}</span>
      </div>
      <div className="flex items-center gap-3 p-2">
        <span className="font-semibold">Email:</span>
        <span>{user.email}</span>
      </div>
    </div>
  );
};
