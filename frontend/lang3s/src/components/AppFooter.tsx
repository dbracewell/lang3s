import { buttonVariants } from "@/components/ui/button";
import {
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import React from "react";

export const AppFooter = () => {
  const router = useRouter();
  return (
    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            className={buttonVariants()}
            onClick={() => {
              authClient.signOut({
                fetchOptions: {
                  onSuccess: () => {
                    sessionStorage.clear();
                    router.push("/sign-in");
                  },
                },
              });
            }}
          >
            Logout
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarFooter>
  );
};
