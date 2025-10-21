import { db } from "@/db";
import { user } from "@/db/schema";
import { InstallPageView } from "@/modules/auth/ui/views/InstallPageView";
import { redirect } from "next/navigation";
import React from "react";

const getUserCount = async () => {
  return await db.$count(user);
};

const InstallPage = async () => {
  const userCount = await getUserCount();
  if (userCount > 0) {
    redirect("/sign-in");
  }
  return <InstallPageView />;
};

export default InstallPage;
