"use client";
import { BasicUserInfo } from "@/lib/types";
import React, { createContext } from "react";
import { NavigationGroup } from "@/lib/navigation";

export const UserContext = createContext<{
  user: BasicUserInfo | null;
  navigation: NavigationGroup[];
}>({
  user: null,
  navigation: [],
});

export const useUser = (): BasicUserInfo => {
  const user = React.useContext(UserContext);
  if (user.user == null) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return user.user;
};

export const useNavigation = (): NavigationGroup[] => {
  const context = React.useContext(UserContext);
  if (context.navigation == null) {
    throw new Error("useNavigation must be used within a UserProvider");
  }
  return context.navigation;
};

export const UserProvider = ({
  user,
  navigation,
  children,
}: {
  user: BasicUserInfo;
  navigation: NavigationGroup[];
  children: React.ReactNode;
}) => {
  return (
    <UserContext.Provider value={{ user, navigation }}>
      {children}
    </UserContext.Provider>
  );
};

export default UserProvider;
