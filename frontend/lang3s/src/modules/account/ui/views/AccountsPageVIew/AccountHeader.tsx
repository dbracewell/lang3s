import { CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FullUserInfo } from "@/modules/common/types";
import { ShieldUserIcon, User2Icon } from "lucide-react";
import React from "react";

export const AccountHeader = ({ user }: { user: FullUserInfo }) => {
  return (
    <CardHeader>
      <CardTitle className="flex items-center gap-3 text-4xl">
        {user.role === "admin" ? <ShieldUserIcon /> : <User2Icon />}
        {user.name}
      </CardTitle>
      <CardDescription>Role: {user.role.toUpperCase()}</CardDescription>
    </CardHeader>
  );
};
