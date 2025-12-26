import { FullUserInfo } from "@/features/common/types";
import { ShieldUserIcon, User2Icon } from "lucide-react";
import React from "react";

export const AccountHeader = ({ user }: { user: FullUserInfo }) => {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="flex items-center gap-3 text-4xl">
        {user.role === "admin" ? <ShieldUserIcon /> : <User2Icon />}
        {user.name}
      </h1>
      <p className="text-muted-foreground text-sm">
        Role: {user.role.toUpperCase()}
      </p>
    </div>
  );
};
