"use client";
import { BasicUserInfo } from "@/features/common/types";
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

export const UserProvider = ({
  user,
  children,
}: {
  user: BasicUserInfo;
  children: React.ReactNode;
}) => {
  return (
    <UserContext.Provider value={{ user }}>{children}</UserContext.Provider>
  );
};

export default UserProvider;
