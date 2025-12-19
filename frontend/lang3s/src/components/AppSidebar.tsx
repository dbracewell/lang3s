"use client";
import { AppFooter } from "@/components/AppFooter";
import { DynamicIcon } from "@/components/DynamicIcon";
import { Logo } from "@/components/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils/cn";
import { useUser } from "@/features/auth/UserContext";
import { filterLinks } from "@/features/common/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

export function AppSidebar() {
  const user = useUser();
  const pathname = usePathname();
  const { state } = useSidebar();
  const navigationLinks = useMemo(() => filterLinks(user.role), [user.role]);

  return (
    <Sidebar collapsible="icon" className="scrollable">
      <div className="flex flex-1 flex-col justify-between bg-gradient-to-b from-zinc-100 to-zinc-200">
        <SidebarHeader className="h-16 py-5">
          <Link href="/" className="mobile:flex mx-auto hidden items-center">
            <Logo height={30} className="fill-dodger-blue-500" />
            <span
              className={cn(
                "ml-1.5 text-2xl font-bold text-zinc-950",
                state === "collapsed" && "hidden",
              )}
            >
              Lang
            </span>
            <span
              className={cn(
                "text-dodger-blue-500 text-2xl font-bold",
                state === "collapsed" && "hidden",
              )}
            >
              3
            </span>
            <span
              className={cn(
                "text-2xl font-bold text-zinc-950",
                state === "collapsed" && "hidden",
              )}
            >
              s
            </span>
          </Link>
        </SidebarHeader>
        <SidebarContent className="mt-4 bg-transparent">
          {navigationLinks.map((section) => {
            return (
              <SidebarGroup key={section.title}>
                <div className="overflow-clip rounded-t-lg rounded-b-md border">
                  <SidebarGroupLabel className="from-dodger-blue-600 to-dodger-blue-800 items-center justify-center gap-2 rounded-none bg-gradient-to-b text-lg text-white">
                    <DynamicIcon
                      name={section.icon}
                      className="size-6 stroke-white stroke-2"
                    />
                    {section.title}
                  </SidebarGroupLabel>

                  <SidebarGroupContent
                    className={cn(state === "expanded" && "bg-white p-2")}
                  >
                    <SidebarMenu
                      className={cn(state === "collapsed" && "gap-0!")}
                    >
                      {section.links.map((link, i) => {
                        if (link.separator) {
                          return (
                            <div key={i} className="bg-border h-[1px] w-full" />
                          );
                        }
                        return (
                          <SidebarMenuItem key={link.href}>
                            <SidebarMenuButton
                              tooltip={link.title}
                              asChild
                              isActive={
                                link.exact
                                  ? pathname === link.href
                                  : pathname.startsWith(link.href)
                              }
                              className={cn(
                                "rounded",
                                state === "collapsed" &&
                                  i === 0 &&
                                  "rounded-b-none",
                                state === "collapsed" &&
                                  i === section.links.length - 1 &&
                                  "rounded-t-none",
                                state === "collapsed" &&
                                  i > 0 &&
                                  i < section.links.length - 1 &&
                                  "rounded-none",
                              )}
                            >
                              <Link href={link.href}>
                                <DynamicIcon
                                  name={link.icon}
                                  className={cn(
                                    "size-6 stroke-black stroke-2",
                                    link.exact
                                      ? pathname === link.href
                                      : pathname.startsWith(link.href) &&
                                          "stroke-white",
                                  )}
                                />
                                <span>{link.title}</span>
                              </Link>
                            </SidebarMenuButton>
                          </SidebarMenuItem>
                        );
                      })}
                    </SidebarMenu>
                  </SidebarGroupContent>
                </div>
              </SidebarGroup>
            );
          })}
        </SidebarContent>
        <AppFooter />
      </div>
    </Sidebar>
  );
}
