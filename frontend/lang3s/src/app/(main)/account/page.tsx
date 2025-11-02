import { AccountPageView } from "@/modules/account/ui/views/AccountsPageVIew";
import { getUser } from "@/modules/auth/server/actions";
import { FullUserInfo } from "@/modules/common/types";
import { caller } from "@/trpc/server";
import React from "react";

const UserPage = async () => {
  const user = await caller.auth.getAccount();
  return <AccountPageView user={user as FullUserInfo} />;
};

export default UserPage;
