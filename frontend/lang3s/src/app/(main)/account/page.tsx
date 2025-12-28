import { AccountPageView } from "@/features/auth/ui/views/AccountsPageVIew";
import { FullUserInfo } from "@/features/common/types";
import { caller } from "@/lib/trpc/server";
import React from "react";

const UserPage = async () => {
  const user = await caller.auth.getAccount();
  return <AccountPageView user={user as FullUserInfo} />;
};

export default UserPage;
