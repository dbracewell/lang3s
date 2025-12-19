"use client";
import { Spinner } from "@/components/Spinner";
import { BasicUserInfo } from "@/features/common/types";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import React, { createContext } from "react";

export const UserContext = createContext<{
  user: BasicUserInfo | null;
}>({
  user: null,
});

export const useUser = (): BasicUserInfo => {
  const user = React.useContext(UserContext);
  if (user.user == null) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return user.user;
};

export const UserProvider = ({ children }: { children: React.ReactNode }) => {
  const { data: user, isPending } = useTRPCQuery((trpc) =>
    trpc.auth.getCurrentUser.queryOptions(undefined, {
      staleTime: 30 * 60 * 1000,
    }),
  );
  if (isPending || user == null) {
    return <Spinner />;
  }
  return (
    <UserContext.Provider value={{ user }}>{children}</UserContext.Provider>
  );
};

export default UserProvider;
