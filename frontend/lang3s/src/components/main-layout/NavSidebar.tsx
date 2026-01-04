"use client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { ChevronRightIcon, XIcon } from "lucide-react";
import { Logo } from "@/components/logo";
import * as React from "react";
import { useNavigation } from "@/features/common/navigation";
import Link from "next/link";
import { DynamicIcon } from "@/components/DynamicIcon";
import { usePathname } from "next/navigation";
import useClickOutside from "@/hooks/useClickOutside";
import { useMemo, useRef } from "react";
import { UserButton } from "@/components/buttons/UserButton";
import { useUser } from "@/features/auth/contexts/UserContext";
import { capitalize } from "@/lib/utils/formatters";

type NavSidebarProps = {
  isOpen: boolean;
  setIsOpen: (value: boolean) => void;
};

export const NavSidebar = ({ isOpen, setIsOpen }: NavSidebarProps) => {
  const navigationLinks = useNavigation();
  const pathname = usePathname();
  const user = useUser();
  const sheetRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);
  useClickOutside([sheetRef, userMenuRef], () => setIsOpen(false));

  const openSection = useMemo(() => {
    return navigationLinks.find((section) =>
      section.links.some(
        (link) =>
          !link.separator &&
          (link.exact
            ? pathname === link.href
            : pathname.startsWith(link.href)),
      ),
    );
  }, [pathname, navigationLinks]);

  return (
    <div
      ref={sheetRef}
      className={cn(
        "mobile:w-[300px] from-sidebar-light to-sidebar-dark shadow-shadow scrollable fixed top-0 left-0 z-50 flex h-screen w-full flex-col border-r bg-linear-to-b transition-all",
        isOpen ? "animate-in translate-x-0 shadow-2xl" : "-translate-x-full",
      )}
    >
      <div className="mt-3 flex items-center px-2">
        <div className="mx-auto flex flex-1 items-center justify-center gap-2 font-bold">
          <Logo
            height={22}
            className="group-hover:fill-white dark:fill-white"
          />{" "}
          <span className="text-xl font-bold select-none">Lang3s</span>
        </div>
        <div className="flex items-center justify-end">
          <Button
            variant="menu"
            size="icon-sm"
            onClick={() => setIsOpen(false)}
          >
            <XIcon className="" />
          </Button>
        </div>
      </div>
      <div className="mt-5 flex flex-1 flex-col gap-2">
        {navigationLinks.map((section) => (
          <details
            key={section.title}
            className="group select-none"
            open={openSection?.title === section.title}
          >
            <summary className="group/a flex cursor-pointer items-center gap-3 bg-zinc-400/30 p-1.5 hover:text-white dark:bg-zinc-700/50">
              <ChevronRightIcon className="size-4 group-open:rotate-90" />
              <DynamicIcon
                name={section.icon}
                className="group-hover/a:stroke-white dark:stroke-white"
              />
              {section.title}
            </summary>
            <div className="flex flex-col">
              {section.links.map((link, i) => {
                if (link.separator) {
                  return (
                    <div
                      className="dark:bg-border my-1 h-px w-full bg-zinc-400"
                      key={i}
                    />
                  );
                }
                const isActive = link.exact
                  ? pathname === link.href
                  : pathname.startsWith(link.href);
                return (
                  <Link
                    key={link.title}
                    href={link.href}
                    className={cn(
                      "flex items-center gap-2 px-8 py-1.5",
                      isActive
                        ? "bg-dodger-blue-500 focus:bg-dodger-blue-500/80 text-sm text-white focus:text-white"
                        : "hover:bg-accent hover:text-accent-foreground",
                    )}
                  >
                    <DynamicIcon
                      name={link.icon}
                      className={cn(
                        "dark:stroke-white",
                        isActive && "stroke-white",
                      )}
                    />
                    {link.title}
                  </Link>
                );
              })}
            </div>
          </details>
        ))}
      </div>
      <div className="flex flex-col gap-2 p-5">
        <UserButton align="center" showArrow={false} ref={userMenuRef}>
          <div className="bg-dodger-blue-500 border-dodger-blue-600 dark:border-dodger-blue-900 flex items-center justify-center rounded-md border-2 py-1 text-white hover:outline-2">
            {capitalize(user.name)}
          </div>
        </UserButton>
      </div>
    </div>
  );
};
