import { Button } from "@/components/ui/button";
import { MenuIcon } from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import * as React from "react";
import { Suspense, useMemo } from "react";
import Link from "next/link";
import { filterLinks, NavigationGroup } from "@/features/common/navigation";
import { useUser } from "@/features/auth/UserContext";
import { DynamicIcon } from "@/components/DynamicIcon";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";
import { SearchBar } from "@/features/search/ui/components/SearchBar";
import { UserButton } from "@/components/buttons/UserButton";

type MenuBarProps = {
  setIsMenuOpen: (value: boolean) => void;
};

export const MenuBar = ({ setIsMenuOpen }: MenuBarProps) => {
  const user = useUser();
  const navigationLinks = useMemo(() => filterLinks(user.role), [user.role]);

  return (
    <div className="flex h-10 items-center gap-2 py-1 pl-2">
      <Button variant="menu" size="icon-xs" onClick={() => setIsMenuOpen(true)}>
        <MenuIcon />
      </Button>
      <Link
        href="/"
        className="hover:border-dodger-blue-700 hover:bg-dodger-blue-500 group flex items-center gap-2 rounded border border-transparent px-5 transition-all hover:text-white hover:inset-shadow-sm hover:inset-shadow-blue-300"
      >
        <Logo height={16} className="group-hover:fill-white dark:fill-white" />{" "}
        <span className="font-bold select-none">Lang3s</span>
      </Link>
      <div className="-gap-2 hidden items-center gap-1 text-sm font-medium sm:flex">
        {navigationLinks.map((section) => (
          <Menu key={section.title} section={section} />
        ))}
      </div>
      <Suspense>
        <SearchBar />
      </Suspense>
      <div className="flex flex-1 items-center justify-end pr-3">
        <UserButton />
      </div>
    </div>
  );
};

const Menu = ({ section }: { section: NavigationGroup }) => {
  const pathname = usePathname();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild className="group">
        <Button variant="menu-item" size="sm" className="group">
          <DynamicIcon
            name={section.icon}
            className="group-hover:stroke-white group-data-[state=open]:stroke-white dark:stroke-white"
          />
          {section.title}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center">
        <div className="dropdown-arrow"></div>
        {section.links.map((link, i) => {
          if (link.separator) {
            return <DropdownMenuSeparator key={i} />;
          }
          const isActive = link.exact
            ? pathname === link.href
            : pathname.startsWith(link.href);
          return (
            <DropdownMenuItem
              key={i}
              className={cn(
                "",
                isActive &&
                  "bg-dodger-blue-500 focus:bg-dodger-blue-500/80 text-white focus:text-white",
              )}
              asChild
            >
              <Link
                href={link.href}
                className="flex w-full cursor-pointer items-center gap-2"
              >
                <DynamicIcon
                  name={link.icon}
                  className={cn(
                    "group-hover:stroke-white dark:stroke-white",
                    isActive && "stroke-white",
                  )}
                />
                {link.title}
              </Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
