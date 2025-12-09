import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { XIcon } from "lucide-react";
import { Logo } from "@/components/logo";
import * as React from "react";

type NavSidebarProps = {
  isOpen: boolean;
  setIsOpen: (value: boolean) => void;
};

export const NavSidebar = ({ isOpen, setIsOpen }: NavSidebarProps) => {
  return (
    <div
      className={cn(
        "mobile:w-[300px] from-sidebar-light to-sidebar-dark fixed top-0 left-0 z-50 flex h-screen w-full flex-col border-r bg-linear-to-b shadow-2xl transition-all",
        isOpen ? "animate-in translate-x-0" : "-translate-x-full",
      )}
    >
      <div className="mt-3 flex items-center justify-between px-2">
        <div className="flex items-center gap-2 text-sm font-bold">
          <Logo
            height={16}
            className="group-hover:fill-white dark:fill-white"
          />{" "}
          <span className="font-bold select-none">Lang3s</span>
        </div>
        <div className="flex w-full flex-1 items-center justify-end">
          <Button
            variant="menu"
            size="icon-xs"
            onClick={() => setIsOpen(false)}
          >
            <XIcon className="" />
          </Button>
        </div>
      </div>
    </div>
  );
};
