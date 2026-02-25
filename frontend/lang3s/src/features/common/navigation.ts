import { Permission } from "@/lib/auth/permissions";
import { useTRPCQuery } from "@/lib/trpc/use-queries";

export type NavigationLink = {
  href: string;
  title: string;
  icon: string;
  exact?: boolean;
  separator?: false;
  permissions?: Permission[];
};

export type NavigationSeparator = {
  separator: true;
};

export type NavigationItem = NavigationLink | NavigationSeparator;

export type NavigationGroup = {
  title: string;
  icon: string;
  links: NavigationItem[];
  permissions?: Permission[];
};

export const NAVIGATION_LINKS: NavigationGroup[] = [
  {
    title: "Explore",
    icon: "BinocularsIcon",
    links: [
      {
        href: "/documents",
        title: "Documents",
        icon: "FileIcon",
        exact: false,
      },
      {
        href: "/analytics/entities",
        title: "Entities",
        icon: "HatGlassesIcon",
        exact: false,
      },
      {
        href: "/analytics/cohorts",
        title: "Cohorts",
        icon: "UsersRoundIcon",
        exact: false,
      },
      { separator: true },
      {
        href: "/analytics/topics",
        title: "Topics",
        icon: "ChartNoAxesGanttIcon",
        exact: false,
      },
      {
        href: "/analytics/concepts",
        title: "Concepts",
        icon: "MessageSquareIcon",
        exact: false,
      },
      { separator: true },
      // {
      //   href: "/kb",
      //   title: "Knowledge Base",
      //   icon: "DatabaseIcon",
      //   exact: false,
      // },

      {
        href: "/system/ontology/viewer",
        title: "Ontology",
        icon: "NetworkIcon",
        exact: false,
      },
    ],
  },
  {
    title: "Build",
    icon: "HammerIcon",
    permissions: [
      "data:load",
      "data:update",
      "model:create",
      "model:delete",
      "model:export",
    ],
    links: [
      {
        href: "/system/jobs",
        title: "Jobs",
        exact: false,
        icon: "HardHatIcon",
        permissions: ["jobs:view"],
      },
      { separator: true },
      {
        href: "/system/metadata",
        title: "Metadata Editor",
        exact: false,
        icon: "FileBracesCornerIcon",
        permissions: ["metadata:edit"],
      },
      {
        href: "/system/ontology/editor",
        title: "Ontology Editor",
        exact: false,
        icon: "NetworkIcon",
        permissions: ["ontology:edit"],
      },
    ],
  },
  {
    title: "Report",
    icon: "NotebookPenIcon",
    links: [
      // {
      //   href: "/notes",
      //   title: "Notes",
      //   exact: false,
      //   icon: "NotebookTextIcon",
      // },
      {
        href: "/reports/charts",
        title: "Charts",
        icon: "ChartAreaIcon",
      },
    ],
  },
  {
    title: "Admin",
    permissions: ["user:list"],
    icon: "ShieldIcon",
    links: [
      {
        href: "/admin",
        exact: true,
        title: "Admin Console",
        icon: "CogIcon",
      },
      {
        href: "/admin/users",
        exact: false,
        title: "User Management",
        icon: "UserCircleIcon",
      },
    ],
  },
];

export const useNavigation = () => {
  const { data, isPending } = useTRPCQuery((trpc) =>
    trpc.auth.getNavigation.queryOptions(),
  );

  if (isPending || data == null) {
    return NAVIGATION_LINKS.filter((g) => g.permissions == null).map((g) => ({
      ...g,
      links: g.links.filter((l) => l.separator || l.permissions == null),
    })) as NavigationGroup[];
  }

  return data;
};
