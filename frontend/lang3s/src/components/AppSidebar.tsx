"use client";
import { Logo } from "@/components/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import {
  BinocularsIcon,
  ChartNoAxesGanttIcon,
  DatabaseIcon,
  FileIcon,
  HammerIcon,
  HardHatIcon,
  HatGlassesIcon,
  NetworkIcon,
  NotebookPenIcon,
  NotebookTextIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAVIGATION_LINKS = [
  {
    title: "Explore",
    icon: BinocularsIcon,
    links: [
      {
        href: "/documents",
        title: "Documents",
        icon: FileIcon,
      },
      {
        href: "/entities",
        title: "Entities",
        icon: HatGlassesIcon,
      },
      {
        href: "/topics",
        title: "Topics",
        icon: ChartNoAxesGanttIcon,
      },
      {},
      {
        href: "/kb",
        title: "Knowledge Base",
        icon: DatabaseIcon,
      },

      {
        href: "/ontology",
        title: "Ontology",
        icon: NetworkIcon,
      },
    ],
  },
  {
    title: "Build",
    icon: HammerIcon,
    links: [
      {
        href: "/documents",
        title: "Documents",
        icon: FileIcon,
      },
      {
        href: "/entities",
        title: "Entities",
        icon: HatGlassesIcon,
      },
      {},
      {
        href: "/jobs",
        title: "Jobs",
        icon: HardHatIcon,
      },
    ],
  },
  {
    title: "Report",
    icon: NotebookPenIcon,
    links: [
      {
        href: "/notes",
        title: "Notes",
        icon: NotebookTextIcon,
      },
    ],
  },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { state } = useSidebar();

  return (
    <Sidebar collapsible="icon" className="border-r p-0!">
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
      <SidebarContent className="mt-4 min-h-full bg-gradient-to-b from-zinc-100 to-zinc-200">
        {NAVIGATION_LINKS.map((section) => (
          <SidebarGroup key={section.title}>
            <div className="overflow-clip rounded-t-lg rounded-b-md border">
              <SidebarGroupLabel className="from-dodger-blue-600 to-dodger-blue-800 items-center justify-center gap-2 rounded-none bg-gradient-to-b text-lg text-white">
                <section.icon className="stroke-2" /> {section.title}
              </SidebarGroupLabel>

              <SidebarGroupContent
                className={cn(state === "expanded" && "bg-white p-2")}
              >
                <SidebarMenu className={cn(state === "collapsed" && "gap-0!")}>
                  {section.links.map((link, i) => {
                    if (!link.href) {
                      return (
                        <div key={i} className="bg-border h-[1px] w-full" />
                      );
                    }
                    return (
                      <SidebarMenuItem key={link.href}>
                        <SidebarMenuButton
                          tooltip={link.title}
                          asChild
                          isActive={pathname.startsWith(link.href)}
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
                            <link.icon /> <span>{link.title}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </div>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter />
    </Sidebar>
  );
}
