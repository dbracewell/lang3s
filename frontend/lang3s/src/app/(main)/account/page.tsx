import { AccountPageView } from "@/features/account/ui/views/AccountsPageVIew";
import { getUser } from "@/features/auth/server/actions";
import { FullUserInfo } from "@/features/common/types";
import { caller } from "@/trpc/server";
import React from "react";

const UserPage = async () => {
  const user = await caller.auth.getAccount();
  return <AccountPageView user={user as FullUserInfo} />;
};

export default UserPage;
