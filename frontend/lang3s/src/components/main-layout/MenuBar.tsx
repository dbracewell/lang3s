import { Button } from "@/components/ui/button";
import { BotIcon, MenuIcon } from "lucide-react";
import { Logo } from "@/components/logo";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import * as React from "react";
import { Suspense } from "react";
import Link from "next/link";
import { NavigationGroup, useNavigation } from "@/features/common/navigation";
import { DynamicIcon } from "@/components/DynamicIcon";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";
import { SearchBar } from "@/features/search/ui/components/SearchBar";
import { UserButton } from "@/components/buttons/UserButton";
import { useAnalyticsUpdate } from "@/features/events/hooks/useAnalyticsUpdate";
import { useUser } from "@/features/auth/contexts/UserContext";
import { useAtomValue } from "jotai";
import { currentProjectAtom } from "@/features/projects/store/projectStore";
import { useChatWindowStatus } from "@/features/chat/hooks/useChatWindowStatus";

type MenuBarProps = {
  setIsMenuOpen: (value: boolean) => void;
};

export const MenuBar = ({ setIsMenuOpen }: MenuBarProps) => {
  const navigationLinks = useNavigation();
  const user = useUser();
  const currentProject = useAtomValue(currentProjectAtom);
  const { open: isChatOpen, setOpen: setChatOpen } = useChatWindowStatus();

  useAnalyticsUpdate();
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
      <div className="hidden items-center gap-1 text-sm font-medium sm:flex">
        {navigationLinks.map((section) => (
          <Menu key={section.title} section={section} />
        ))}
      </div>
      <Suspense>
        <SearchBar />
      </Suspense>
      <div className="flex flex-1 items-center justify-end gap-3 pr-3">
        <button
          className={cn(
            "hover:bg-accent outline-dodger-blue-500 flex items-center gap-2 rounded-full px-1.5 py-0.5 hover:outline",
            isChatOpen &&
              "bg-accent outline-dodger-blue-500 hover:bg-dodger-blue-500 flex items-center gap-2 rounded-full px-1.5 py-0.5 outline hover:text-white",
          )}
          onClick={() => setChatOpen((prev) => !prev)}
        >
          <BotIcon className="size-4" /> Agent
        </button>
        <UserButton>
          <div className="bg-dodger-blue-500 border-dodger-blue-600 dark:border-dodger-blue-900 flex size-7 items-center justify-center rounded-full border-2 text-sm text-white hover:outline-2">
            {user.username[0].toUpperCase()}
          </div>
        </UserButton>
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
