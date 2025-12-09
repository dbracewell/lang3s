import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MenuSquareIcon, ShieldIcon } from "lucide-react";

type NavSidebarProps = {
  isOpen: boolean;
  setIsOpen: (value: boolean) => void;
};

export const NavSidebar = ({ isOpen, setIsOpen }: NavSidebarProps) => {
  return (
    <div
      className={cn(
        "from-sidebar-light to-sidebar-dark fixed top-0 left-0 z-50 flex h-screen w-[300px] flex-col border-r bg-linear-to-b p-4 shadow-2xl transition-all",
        isOpen ? "animate-in translate-x-0" : "-translate-x-full",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex flex-1 items-center text-sm font-bold">
          <ShieldIcon className="mr-2 size-4" /> KillerApp
        </div>
        <Button variant="menu" onClick={() => setIsOpen(false)}>
          <MenuSquareIcon className="" />
        </Button>
      </div>
    </div>
  );
};
